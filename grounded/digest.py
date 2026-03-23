"""Orchestrator — fetch, summarize, and render the weekly math digest."""

from __future__ import annotations
import time

import argparse
from datetime import date, timedelta
from pathlib import Path

import anthropic

from grounded.arxiv_client import fetch_papers
from grounded.grouper import group_papers
from grounded.renderer import render_index_page, render_week_page
from grounded.semantic_scholar import enrich_with_hindex
from grounded.summarizer import (
    generate_digest_intro,
    select_papers,
    summarize_all_papers,
)


def _week_label(end: date) -> str:
    start = end - timedelta(days=6)
    if start.month == end.month:
        return f"{start.strftime('%B %-d')}–{end.strftime('%-d, %Y')}"
    return f"{start.strftime('%B %-d')} – {end.strftime('%B %-d, %Y')}"


def run(
    days_back: int = 7,
    output_dir: Path = Path("docs"),
    api_key: str | None = None,
    skip_enrichment: bool = False,
) -> None:
    today = date.today()
    week_slug = today.isoformat()
    week_label = _week_label(today)

    print(f"Fetching all papers from the last {days_back} days...")
    papers = fetch_papers(days_back=days_back)
    print(f"  Found {len(papers)} papers.")

    if not papers:
        print("No papers found. Exiting.")
        return

    # Enrich with Semantic Scholar author h-index
    if skip_enrichment:
        print("Skipping Semantic Scholar enrichment.")
        hindex_map: dict[str, int] = {}
    else:
        print(f"Enriching {len(papers)} papers with Semantic Scholar author h-indices...")
        hindex_map = enrich_with_hindex(papers)
        enriched = sum(1 for v in hindex_map.values() if v > 0)
        print(f"  H-index data found for {enriched}/{len(papers)} papers.")

    # Claude selection pass
    print("Running Claude selection pass...")
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    selected = select_papers(papers, hindex_map, client)
    print(f"  Selected {len(selected)}/{len(papers)} papers for the digest.")

    grouped = group_papers(selected)

    print("Summarizing selected papers with Claude...")
    time.sleep(90)
    summaries, client = summarize_all_papers(selected, client=client)
    print(f"  Summarized {len(summaries)} papers.")

    print("Generating digest introduction...")
    intro = generate_digest_intro(selected, summaries, client, week_label)

    print("Rendering HTML...")
    week_path = render_week_page(
        week_label=week_label,
        week_slug=week_slug,
        intro=intro,
        grouped_papers=grouped,
        summaries=summaries,
        output_dir=output_dir,
    )
    index_path = render_index_page(output_dir=output_dir)

    print(f"Done! Generated digest for {week_label}:")
    print(f"  Week page : {week_path}")
    print(f"  Index     : {index_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a weekly math research digest from arXiv."
    )
    parser.add_argument("--days-back", type=int, default=7)
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        default=False,
        help="Skip Semantic Scholar h-index enrichment (useful for local testing).",
    )
    args = parser.parse_args()
    run(
        days_back=args.days_back,
        output_dir=args.output_dir,
        api_key=args.api_key,
        skip_enrichment=args.skip_enrichment,
    )


if __name__ == "__main__":
    main()
