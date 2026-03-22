"""Fetch recent math papers from the arXiv API."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, timedelta

import requests

MATH_CATEGORIES = [
    "math.AC", "math.AG", "math.AP", "math.AT", "math.CA", "math.CO",
    "math.CT", "math.CV", "math.DG", "math.DS", "math.FA", "math.GM",
    "math.GN", "math.GR", "math.GT", "math.HO", "math.IT", "math.KT",
    "math.LO", "math.MG", "math.MP", "math.NA", "math.NT", "math.OA",
    "math.OC", "math.PR", "math.QA", "math.RA", "math.RT", "math.SG",
    "math.SP", "math.ST",
]

ARXIV_API_URL = "http://export.arxiv.org/api/query"

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    primary_category: str
    all_categories: list[str]
    submitted: date
    url: str = field(init=False)

    def __post_init__(self) -> None:
        self.url = f"https://arxiv.org/abs/{self.arxiv_id}"


def _strip_latex(text: str) -> str:
    """Remove common LaTeX markup to produce plain text."""
    # Remove display math $$...$$
    text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.DOTALL)
    # Remove inline math $...$
    text = re.sub(r"\$.*?\$", "", text, flags=re.DOTALL)
    # Remove \command{...} keeping inner text
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    # Remove bare \command
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_arxiv_id(id_url: str) -> str:
    """Extract '2403.12345' from 'http://arxiv.org/abs/2403.12345v1'."""
    match = re.search(r"abs/(\d{4}\.\d+)", id_url)
    if match:
        return match.group(1)
    # Fallback: return the last path segment stripped of version suffix
    return id_url.rstrip("/").split("/")[-1].split("v")[0]


def _build_query(days_back: int = 7) -> str:
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)
    date_range = f"submittedDate:[{start_date.strftime('%Y%m%d')} TO {end_date.strftime('%Y%m%d')}]"
    cat_filter = " OR ".join(f"cat:{c}" for c in MATH_CATEGORIES)
    return f"({cat_filter}) AND {date_range}"


def fetch_papers(max_results: int = 25, days_back: int = 7) -> list[ArxivPaper]:
    """Fetch recent math papers from arXiv."""
    query = _build_query(days_back)
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    response = requests.get(ARXIV_API_URL, params=params, timeout=30)
    response.raise_for_status()
    time.sleep(3)  # arXiv rate limit courtesy

    root = ET.fromstring(response.content)
    papers: list[ArxivPaper] = []

    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        id_url = entry.findtext(f"{{{ATOM_NS}}}id", "").strip()
        arxiv_id = _parse_arxiv_id(id_url)

        title = re.sub(
            r"\s+", " ",
            (entry.findtext(f"{{{ATOM_NS}}}title") or "").strip()
        )

        abstract = _strip_latex(
            (entry.findtext(f"{{{ATOM_NS}}}summary") or "").strip()
        )

        authors = [
            a.findtext(f"{{{ATOM_NS}}}name", "").strip()
            for a in entry.findall(f"{{{ATOM_NS}}}author")
        ]

        primary_cat_el = entry.find(f"{{{ARXIV_NS}}}primary_category")
        primary_category = (
            primary_cat_el.attrib.get("term", "math.GM")
            if primary_cat_el is not None
            else "math.GM"
        )

        all_categories = [
            c.attrib.get("term", "")
            for c in entry.findall(f"{{{ATOM_NS}}}category")
        ]

        submitted_str = (
            entry.findtext(f"{{{ATOM_NS}}}published") or ""
        ).strip()[:10]
        try:
            submitted = date.fromisoformat(submitted_str)
        except ValueError:
            submitted = date.today()

        if arxiv_id and title and abstract:
            papers.append(
                ArxivPaper(
                    arxiv_id=arxiv_id,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    primary_category=primary_category,
                    all_categories=[c for c in all_categories if c],
                    submitted=submitted,
                )
            )

    return papers
