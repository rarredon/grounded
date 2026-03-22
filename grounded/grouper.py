"""Group arXiv papers by math subfield."""

from __future__ import annotations

from collections import OrderedDict

from grounded.arxiv_client import ArxivPaper

CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    "math.AC": "Commutative Algebra",
    "math.AG": "Algebraic Geometry",
    "math.AP": "Analysis of PDEs",
    "math.AT": "Algebraic Topology",
    "math.CA": "Classical Analysis and ODEs",
    "math.CO": "Combinatorics",
    "math.CT": "Category Theory",
    "math.CV": "Complex Variables",
    "math.DG": "Differential Geometry",
    "math.DS": "Dynamical Systems",
    "math.FA": "Functional Analysis",
    "math.GM": "General Mathematics",
    "math.GN": "General Topology",
    "math.GR": "Group Theory",
    "math.GT": "Geometric Topology",
    "math.HO": "History and Overview",
    "math.IT": "Information Theory",
    "math.KT": "K-Theory and Homology",
    "math.LO": "Logic",
    "math.MG": "Metric Geometry",
    "math.MP": "Mathematical Physics",
    "math.NA": "Numerical Analysis",
    "math.NT": "Number Theory",
    "math.OA": "Operator Algebras",
    "math.OC": "Optimization and Control",
    "math.PR": "Probability",
    "math.QA": "Quantum Algebra",
    "math.RA": "Rings and Algebras",
    "math.RT": "Representation Theory",
    "math.SG": "Symplectic Geometry",
    "math.SP": "Spectral Theory",
    "math.ST": "Statistics Theory",
}

# High-interest categories first, then alphabetical remainder
CATEGORY_ORDER = [
    "math.NT", "math.AG", "math.AP", "math.CO", "math.PR",
    "math.DG", "math.GT", "math.NA", "math.MP", "math.AT",
    "math.RT", "math.DS", "math.FA", "math.GR", "math.OC",
    "math.CA", "math.CV", "math.LO", "math.OA", "math.RA",
    "math.AC", "math.CT", "math.QA", "math.SG", "math.SP",
    "math.ST", "math.IT", "math.KT", "math.MG", "math.GN",
    "math.GM", "math.HO",
]


def display_name(category_code: str) -> str:
    return CATEGORY_DISPLAY_NAMES.get(category_code, category_code)


def math_category(paper: ArxivPaper) -> str | None:
    """Return the first math.* category for a paper, or None if it has none."""
    if paper.primary_category.startswith("math."):
        return paper.primary_category
    return next(
        (c for c in paper.all_categories if c.startswith("math.")),
        None,
    )


def group_papers(papers: list[ArxivPaper]) -> OrderedDict[str, list[ArxivPaper]]:
    """Group papers by their first math category, ordered by CATEGORY_ORDER.

    Papers with no math category at all are silently dropped.
    """
    buckets: dict[str, list[ArxivPaper]] = {}
    for paper in papers:
        cat = math_category(paper)
        if cat is None:
            continue
        buckets.setdefault(cat, []).append(paper)

    result: OrderedDict[str, list[ArxivPaper]] = OrderedDict()
    # Add in preferred order first
    for cat in CATEGORY_ORDER:
        if cat in buckets:
            result[cat] = buckets[cat]
    # Then any remaining categories not in the order list
    for cat, ps in buckets.items():
        if cat not in result:
            result[cat] = ps

    return result
