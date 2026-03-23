"""Enrich arXiv papers with author h-index data from Semantic Scholar."""

from __future__ import annotations
from apiclient.errors import HttpError

import time

import requests

from grounded.arxiv_client import ArxivPaper

S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"


def _max_hindex(record: dict | None) -> int:
    """Return the max h-index across all authors in an S2 paper record."""
    if record is None:
        return 0
    authors = record.get("authors") or []
    return max((a.get("hIndex") or 0 for a in authors), default=0)


def enrich_with_hindex(
    papers: list[ArxivPaper],
    batch_size: int = 500,
    request_delay: float = 1.1,
) -> dict[str, int]:
    """Return a mapping of arxiv_id -> max author h-index.

    Papers not yet indexed in Semantic Scholar (common for week-old preprints)
    return 0. All network failures are caught silently — the function never raises.
    """
    hindex_map: dict[str, int] = {p.arxiv_id: 0 for p in papers}
    ids = [p.arxiv_id for p in papers]

    for batch_start in range(0, len(ids), batch_size):
        batch_ids = ids[batch_start : batch_start + batch_size]
        s2_ids = [f"arXiv:{aid}" for aid in batch_ids]
        resp = None
        try:
            resp = requests.post(
                S2_BATCH_URL,
                params={"fields": "authors.hIndex"},
                json={"ids": s2_ids},
                timeout=30,
            )
            resp.raise_for_status()
            records = resp.json()
            # S2 response is positionally aligned with the request ids list
            for arxiv_id, record in zip(batch_ids, records):
                hindex_map[arxiv_id] = _max_hindex(record)
        except HttpError as exc:
            if resp and resp.status_code == 429:
                retries = 1
                while retries <= 3:
                    time.sleep(3*2**retries)
                    resp = None
                    try:
                        resp = requests.post(
                            S2_BATCH_URL,
                            params={"fields": "authors.hIndex"},
                            json={"ids": s2_ids},
                            timeout=30,
                        )
                        resp.raise_for_status()
                        records = resp.json()
                        # S2 response is positionally aligned with the request ids list
                        for arxiv_id, record in zip(batch_ids, records):
                            hindex_map[arxiv_id] = _max_hindex(record)
                    except HttpError:
                        if resp is None or resp.status_code != 429 or retries == 3:
                            raise

                    retries += 1

        time.sleep(request_delay)

    return hindex_map
