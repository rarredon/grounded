"""Summarize math papers using the Anthropic API."""

from __future__ import annotations

import json
import re
import time

import anthropic

from grounded.arxiv_client import ArxivPaper

MODEL = "claude-sonnet-4-6"

PAPER_BATCH_SYSTEM_PROMPT = """\
You are a science communicator writing for readers who have a bachelor's \
degree in mathematics but are not specialists in every subfield. \
For each paper provided, write a summary that:
- Explains the paper's core question and its key result in 2-3 sentences
- Defines any specialized terms you use
- Conveys why the result matters or what open problem it addresses
- Is direct and engaging, not academic in tone
- Is 60-80 words maximum — brevity is essential

Respond with ONLY a valid JSON object mapping each arxiv_id to its summary string:
{"2403.12345": "summary text...", "2501.00001": "summary text..."}"""

DIGEST_SYSTEM_PROMPT = """\
You are the editor of a weekly mathematics research newsletter called Grounded. \
Write a 3-4 sentence introduction to this week's digest. \
Highlight 2-3 of the most exciting themes or surprising results you see \
across the papers. Write for an intelligent audience with a math background. \
Be enthusiastic but precise. Do not quote paper titles directly."""

SELECTION_SYSTEM_PROMPT = """\
You are a senior mathematician and research editor curating a weekly digest of \
arXiv math preprints for a mathematically literate audience.

You will be given a manifest of papers, one per line, in the format:
[arxiv_id] [category] (h:{max_author_hindex}) "Title" — abstract snippet

Your task is to select the papers that represent genuine mathematical advances \
worth highlighting. Use the following criteria:

1. SIGNIFICANCE: Does the paper state a concrete result — a theorem, classification, \
   algorithm, or sharp bound — rather than just a survey or incremental note?
2. NOVELTY: Does the result appear to resolve a known open problem, introduce a new \
   technique, or establish a surprising connection between subfields?
3. CLARITY OF CONTRIBUTION: Is the stated contribution specific and verifiable from \
   the title and abstract alone, not vague or self-aggrandizing?
4. AUTHOR REPUTATION: Higher h-index (h ≥ 20) is a weak positive signal. Do not \
   exclude strong papers by unknown authors — use h-index only as a tiebreaker. \
   Many excellent papers will have h:0 because new preprints lag in indexing.
5. EXCLUSION: Actively exclude papers making extraordinary or unverifiable claims \
   (e.g., claimed proofs of major open conjectures with no evidence of rigor), \
   minor corrections or erratum notices, and papers with no clear mathematical content.

There is no fixed quota. Select as many papers as genuinely merit inclusion — \
typically 20–60 from a pool of several hundred, but follow quality, not a number.

Respond with ONLY a valid JSON object in this exact format, with no prose before or after:
{"selected": ["2403.12345", "2501.00001", ...]}"""


def _parse_selected_ids(raw: str) -> list[str]:
    """Extract the list of arXiv IDs from Claude's JSON response.

    Tries strict parse, then JSON embedded in prose, then bare ID extraction.
    """
    try:
        data = json.loads(raw)
        return [str(x) for x in data.get("selected", [])]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return [str(x) for x in data.get("selected", [])]
        except json.JSONDecodeError:
            pass

    # Last resort: extract anything that looks like an arXiv ID
    return re.findall(r"\b\d{4}\.\d{4,5}\b", raw)


def select_papers(
    papers: list[ArxivPaper],
    hindex_map: dict[str, int],
    client: anthropic.Anthropic,
    abstract_snippet_len: int = 150,
) -> list[ArxivPaper]:
    """Use a single Claude call to select papers worth summarizing.

    Returns the subset Claude identified as significant, in original list order.
    Falls back to returning all papers if Claude's response cannot be parsed
    or yields no results.
    """
    lines = []
    for p in papers:
        snippet = p.abstract[:abstract_snippet_len].replace("\n", " ")
        h = hindex_map.get(p.arxiv_id, 0)
        lines.append(
            f'[{p.arxiv_id}] [{p.primary_category}] (h:{h}) "{p.title}" — {snippet}'
        )
    manifest = "\n".join(lines)

    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SELECTION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Here are {len(papers)} math preprints submitted this week. "
                    f"Select those that represent significant mathematical advances.\n\n"
                    f"{manifest}"
                ),
            }
        ],
    )

    raw = message.content[0].text.strip()
    selected_ids = _parse_selected_ids(raw)

    valid_ids = {p.arxiv_id for p in papers}
    id_set = {aid for aid in selected_ids if aid in valid_ids}

    # Preserve original list order
    selected = [p for p in papers if p.arxiv_id in id_set]

    if not selected:
        print("  [selection] Warning: no papers selected; falling back to all papers.")
        return papers

    return selected


def _parse_summaries(raw: str) -> dict[str, str]:
    """Extract arxiv_id → summary mapping from Claude's JSON response."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def summarize_batch(
    client: anthropic.Anthropic,
    papers: list[ArxivPaper],
    abstract_max_chars: int = 500,
) -> dict[str, str]:
    """Summarize a batch of papers in a single Claude call.

    Returns a dict mapping arxiv_id → plain-English summary.
    Missing entries (parse failures) are silently omitted.
    """
    entries = []
    for p in papers:
        abstract = (
            p.abstract
            if len(p.abstract) <= abstract_max_chars
            else f"{p.abstract[:abstract_max_chars]}... (truncated)"
        )
        entries.append(
            f"Paper {p.arxiv_id} [{p.primary_category}]:\n"
            f"Title: {p.title}\n"
            f"Abstract: {abstract}"
        )
    user_content = "\n\n".join(entries)

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=len(papers) * 200,
            system=PAPER_BATCH_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Summarize these {len(papers)} math papers.\n\n{user_content}"
                    ),
                }
            ],
        )
    except anthropic.RateLimitError as e:
        print(f"Failed with response headers: {e.response.headers}")
        raise

    raw = message.content[0].text.strip()
    result = _parse_summaries(raw)
    if not result:
        ids = [p.arxiv_id for p in papers]
        print(f"  [summarizer] Warning: could not parse batch response for {ids}")
    return result


def summarize_all_papers(
    papers: list[ArxivPaper],
    api_key: str | None = None,
    client: anthropic.Anthropic | None = None,
    batch_size: int = 5,
    inter_batch_delay: float = 6.0,
) -> tuple[dict[str, str], anthropic.Anthropic]:
    """Summarize papers in batches. Returns (summaries dict, client)."""
    if client is None:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    summaries: dict[str, str] = {}
    batches = [papers[i : i + batch_size] for i in range(0, len(papers), batch_size)]
    for batch in batches:
        summaries.update(summarize_batch(client, batch))
        time.sleep(inter_batch_delay)
    return summaries, client


def generate_digest_intro(
    papers: list[ArxivPaper],
    summaries: dict[str, str],
    client: anthropic.Anthropic,
    week_label: str,
) -> str:
    paper_list = "\n".join(
        f"- [{p.primary_category}] {p.title}: {summaries.get(p.arxiv_id, '')}"
        for p in papers
    )
    message = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=DIGEST_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Here are this week's ({week_label}) math papers with summaries:\n\n"
                    f"{paper_list}\n\n"
                    f"Write the weekly introduction."
                ),
            }
        ],
    )
    return message.content[0].text.strip()
