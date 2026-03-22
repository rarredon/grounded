"""Summarize math papers using the Anthropic API."""

from __future__ import annotations

import time

import anthropic

from grounded.arxiv_client import ArxivPaper

MODEL = "claude-sonnet-4-6"

PAPER_SYSTEM_PROMPT = """\
You are a science communicator writing for readers who have a bachelor's \
degree in mathematics but are not specialists in every subfield. \
Your summaries must:
- Explain the paper's core question and its key result in 2-3 sentences
- Define any specialized terms you use
- Convey why the result matters or what open problem it addresses
- Be direct and engaging, not academic in tone
- Be 60-80 words maximum — brevity is essential"""

DIGEST_SYSTEM_PROMPT = """\
You are the editor of a weekly mathematics research newsletter called Grounded. \
Write a 3-4 sentence introduction to this week's digest. \
Highlight 2-3 of the most exciting themes or surprising results you see \
across the papers. Write for an intelligent audience with a math background. \
Be enthusiastic but precise. Do not quote paper titles directly."""


def summarize_paper(client: anthropic.Anthropic, paper: ArxivPaper) -> str:
    message = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=PAPER_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Summarize this math paper for a general math-literate audience.\n\n"
                    f"Title: {paper.title}\n\n"
                    f"Abstract:\n{paper.abstract}"
                ),
            }
        ],
    )
    return message.content[0].text.strip()


def summarize_all_papers(
    papers: list[ArxivPaper],
    api_key: str | None = None,
) -> tuple[dict[str, str], anthropic.Anthropic]:
    """Summarize all papers sequentially. Returns (summaries dict, client)."""
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    summaries: dict[str, str] = {}
    for i, paper in enumerate(papers):
        summaries[paper.arxiv_id] = summarize_paper(client, paper)
        if i < len(papers) - 1:
            time.sleep(0.5)
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
