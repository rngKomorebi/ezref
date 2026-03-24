"""API clients for CrossRef and arXiv."""

import re
import urllib.parse
import urllib.request
from typing import Optional

import feedparser
import requests

from config import (
    ARXIV_API_URL,
    ARXIV_TIMEOUT,
    CROSSREF_API_URL,
    CROSSREF_TIMEOUT,
)


def get_crossref_by_doi(doi: str) -> Optional[dict]:
    """
    Get paper metadata from CrossRef using DOI.

    Args:
        doi: Digital Object Identifier

    Returns:
        CrossRef item dict or None if not found
    """
    try:
        url = f"{CROSSREF_API_URL}/{doi}"
        response = requests.get(url, timeout=CROSSREF_TIMEOUT)
        if response.status_code == 200:
            return response.json().get("message")
        return None
    except Exception as e:
        print(f"CrossRef DOI lookup error: {e}")
        return None


def search_crossref_by_citation(
    journal: str, volume: str, issue: str, page: str
) -> list[dict]:
    """
    Search CrossRef by bibliographic citation details.

    Args:
        journal: Journal name
        volume: Volume number
        issue: Issue number
        page: Page number

    Returns:
        List of matching CrossRef items
    """
    strategies = [
        {
            "query.bibliographic": f"{journal} volume {volume} page {page}",
            "rows": 50,
        },
        {
            "query.container-title": journal,
            "query.bibliographic": str(page),
            "rows": 100,
        },
    ]

    for params in strategies:
        try:
            response = requests.get(
                CROSSREF_API_URL, params=params, timeout=CROSSREF_TIMEOUT
            )
            response.raise_for_status()
            items = response.json().get("message", {}).get("items", [])

            for item in items:
                item_vol = str(item.get("volume", ""))
                item_issue = str(item.get("issue", ""))
                item_page = str(item.get("page", ""))

                if (
                    item_vol == volume
                    and item_issue == issue
                    and page in item_page
                ):
                    return [item]
        except Exception:
            continue

    return []


def search_crossref_by_title(title: str) -> Optional[dict]:
    """
    Search CrossRef by paper title.

    Returns the best-matching item, or None if no confident match found.
    """
    try:
        params = {"query.title": title, "rows": 5}
        response = requests.get(
            CROSSREF_API_URL, params=params, timeout=CROSSREF_TIMEOUT
        )
        response.raise_for_status()
        items = response.json().get("message", {}).get("items", [])
        title_words = set(re.sub(r"[^a-z0-9]", " ", title.lower()).split())
        for item in items:
            item_title = item.get("title", [""])[0]
            item_words = set(
                re.sub(r"[^a-z0-9]", " ", item_title.lower()).split()
            )
            if title_words and (
                len(title_words & item_words) / len(title_words) >= 0.7
            ):
                return item
    except Exception as e:
        print(f"CrossRef title search error: {e}")
    return None


def get_from_arxiv(query: str) -> Optional[dict]:
    """
    Search arXiv API by ID or title.

    Args:
        query: arXiv ID (e.g., "2301.12345") or paper title

    Returns:
        arXiv entry dict or None if not found
    """
    # Check if input is an arXiv ID
    arxiv_id_pattern = r"^\d{4}\.\d{4,5}(v\d+)?$"
    is_arxiv_id = re.match(arxiv_id_pattern, query.strip())

    if is_arxiv_id:
        params = {"id_list": query.strip(), "start": 0, "max_results": 1}
    else:
        params = {"search_query": query, "start": 0, "max_results": 5}

    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=ARXIV_TIMEOUT) as response:
            xml_data = response.read().decode("utf-8")
    except Exception as e:
        print(f"arXiv API error: {e}")
        return None

    feed = feedparser.parse(xml_data)

    if not feed.entries:
        return None

    # If searching by ID, return first result directly
    if is_arxiv_id:
        return feed.entries[0]

    # For title search, check similarity
    query_lower = query.lower().strip()
    for entry in feed.entries:
        entry_title = entry.get("title", "").lower().strip()

        # Clean titles for comparison
        query_clean = re.sub(r"[^a-z0-9\s]", "", query_lower)
        entry_clean = re.sub(r"[^a-z0-9\s]", "", entry_title)
        query_clean = " ".join(query_clean.split())
        entry_clean = " ".join(entry_clean.split())

        # Check word overlap (80% threshold)
        query_words = set(query_clean.split())
        entry_words = set(entry_clean.split())

        if len(query_words) > 0:
            overlap = len(query_words & entry_words) / len(query_words)
            if overlap >= 0.8:
                return entry

    return None
