"""Render weekly digest HTML using Jinja2 templates."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import jinja2

from grounded.arxiv_client import ArxivPaper
from grounded.grouper import display_name

_env: jinja2.Environment | None = None


def _get_env() -> jinja2.Environment:
    global _env
    if _env is None:
        templates_dir = Path(__file__).parent.parent / "templates"
        _env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            autoescape=jinja2.select_autoescape(["html"]),
        )
        _env.globals["display_name"] = display_name
    return _env


def render_week_page(
    week_label: str,
    week_slug: str,
    intro: str,
    grouped_papers: OrderedDict[str, list[ArxivPaper]],
    summaries: dict[str, str],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = _get_env()
    template = env.get_template("week.html")
    html = template.render(
        week_label=week_label,
        week_slug=week_slug,
        intro=intro,
        grouped_papers=grouped_papers,
        summaries=summaries,
        total_papers=sum(len(ps) for ps in grouped_papers.values()),
    )
    out_path = output_dir / f"{week_slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_index_page(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    weeks = []
    for html_file in sorted(output_dir.glob("????-??-??.html"), reverse=True):
        slug = html_file.stem  # e.g. "2026-03-21"
        try:
            from datetime import date
            d = date.fromisoformat(slug)
            label = d.strftime("%B %-d, %Y")
        except ValueError:
            label = slug
        # Count paper sections as a proxy for paper count (rough)
        weeks.append({"slug": slug, "label": label})

    env = _get_env()
    template = env.get_template("index.html")
    html = template.render(weeks=weeks)
    out_path = output_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
