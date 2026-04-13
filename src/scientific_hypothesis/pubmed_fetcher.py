"""PubMed E-utilities fetcher using only Python standard library (urllib).

API reference: https://www.ncbi.nlm.nih.gov/books/NBK25499/
All HTTP calls use urllib.request — no external dependencies.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any

ESEARCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ESUMMARY_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

_REQUEST_DELAY = 0.4  # NCBI rate limit: max 3 requests/sec without API key


def _get(url: str, timeout: int = 20) -> bytes:
    """Perform an HTTP GET and return raw bytes."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "kg-discovery-engine/1.0 (mailto:research@example.com)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def esearch_count(query: str, db: str = "pubmed",
                  date_from: str | None = None, date_to: str | None = None) -> int:
    """Return total hit count for the given query (no records fetched).

    Args:
        query: PubMed search string.
        db: Entrez database (default "pubmed").
        date_from: Inclusive start date string "YYYY/MM/DD".
        date_to: Inclusive end date string "YYYY/MM/DD".

    Returns:
        Integer hit count reported by E-utilities.
    """
    params: dict[str, str] = {
        "db": db,
        "term": query,
        "retmode": "json",
        "rettype": "count",
        "retmax": "0",
    }
    if date_from:
        params["mindate"] = date_from
    if date_to:
        params["maxdate"] = date_to
    if date_from or date_to:
        params["datetype"] = "pdat"

    url = ESEARCH_BASE + "?" + urllib.parse.urlencode(params)
    raw = _get(url)
    data: dict[str, Any] = json.loads(raw)
    count = int(data["esearchresult"]["count"])
    time.sleep(_REQUEST_DELAY)
    return count


def esearch_ids(query: str, db: str = "pubmed", retmax: int = 20,
                date_from: str | None = None, date_to: str | None = None) -> list[str]:
    """Return a list of PubMed IDs matching the query.

    Args:
        query: PubMed search string.
        db: Entrez database.
        retmax: Maximum number of IDs to return (≤10 000).
        date_from: Inclusive start date "YYYY/MM/DD".
        date_to: Inclusive end date "YYYY/MM/DD".

    Returns:
        List of PubMed ID strings.
    """
    params: dict[str, str] = {
        "db": db,
        "term": query,
        "retmode": "json",
        "retmax": str(retmax),
    }
    if date_from:
        params["mindate"] = date_from
    if date_to:
        params["maxdate"] = date_to
    if date_from or date_to:
        params["datetype"] = "pdat"

    url = ESEARCH_BASE + "?" + urllib.parse.urlencode(params)
    raw = _get(url)
    data: dict[str, Any] = json.loads(raw)
    ids: list[str] = data["esearchresult"].get("idlist", [])
    time.sleep(_REQUEST_DELAY)
    return ids


def esummary_titles(pmids: list[str], db: str = "pubmed") -> list[dict[str, str]]:
    """Fetch title and date for a list of PubMed IDs via ESummary.

    Args:
        pmids: List of PubMed ID strings (max 200 per call recommended).
        db: Entrez database.

    Returns:
        List of dicts with keys: pmid, title, pubdate.
    """
    if not pmids:
        return []
    params = {
        "db": db,
        "id": ",".join(pmids),
        "retmode": "json",
    }
    url = ESUMMARY_BASE + "?" + urllib.parse.urlencode(params)
    raw = _get(url)
    data: dict[str, Any] = json.loads(raw)
    results = data.get("result", {})
    uids: list[str] = results.get("uids", [])

    records: list[dict[str, str]] = []
    for uid in uids:
        entry = results.get(uid, {})
        records.append({
            "pmid": uid,
            "title": entry.get("title", ""),
            "pubdate": entry.get("pubdate", ""),
            "source": entry.get("source", ""),
        })
    time.sleep(_REQUEST_DELAY)
    return records
