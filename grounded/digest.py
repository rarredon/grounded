"""Orchestrator — fetch, summarize, and render the weekly math digest."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from grounded.arxiv_client import fetch_papers
from grounded.grouper import group_papers
from grounded.renderer import render_index_page, render_week_page
from grounded.summarizer import generate_digest_intro, summarize_all_papers


def _week_label(end: date) -> str:
    start = end - timedelta(days=6)
    if start.month == end.month:
        return f"{start.strftime('%B %-d')}–{end.strftime('%-d, %Y')}"
    return f"{start.strftime('%B %-d')} – {end.strftime('%B %-d, %Y')}"


def run(
    max_papers: int = 25,
    days_back: int = 7,
    output_dir: Path = Path("docs"),
    api_key: str | None = None,
) -> None:
    today = date.today()
    week_slug = today.isoformat()
    week_label = _week_label(today)

    print(f"Fetching up to {max_papers} papers from the last {days_back} days...")
    papers = fetch_papers(max_results=max_papers, days_back=days_back)
    print(f"  Found {len(papers)} papers.")

    if not papers:
        print("No papers found. Exiting.")
        return

    grouped = group_papers(papers)

    print("Summarizing papers with Claude...")
    summaries, client = summarize_all_papers(papers, api_key=api_key)
    print(f"  Summarized {len(summaries)} papers.")

    print("Generating digest introduction...")
    intro = generate_digest_intro(papers, summaries, client, week_label)

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
    parser.add_argument("--max-papers", type=int, default=25)
    parser.add_argument("--days-back", type=int, default=7)
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    parser.add_argument("--api-key", type=str, default=None)
    args = parser.parse_args()
    run(
        max_papers=args.max_papers,
        days_back=args.days_back,
        output_dir=args.output_dir,
        api_key=args.api_key,
    )


if __name__ == "__main__":
    main()
