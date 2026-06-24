"""Parsers for extracting DOIs, arXiv IDs, and metadata from URLs and PDFs."""

import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import (
    ARXIV_PATTERNS,
    DEFAULT_HEADERS,
    DOI_PATTERNS,
    OPTICA_JOURNALS,
    PDF_DOWNLOAD_SIZE,
    PDF_DOWNLOAD_TIMEOUT,
    URL_FETCH_TIMEOUT,
)


def extract_arxiv_id(text: str) -> Optional[str]:
    """
    Extract arXiv ID from URL or text.

    Args:
        text: Input text containing arXiv URL or ID

    Returns:
        arXiv ID (e.g., "2301.12345") or None
    """
    for pattern in ARXIV_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def extract_doi(text: str) -> Optional[str]:
    """
    Extract DOI from URL or text.

    Args:
        text: Input text containing DOI URL or DOI

    Returns:
        DOI string (e.g., "10.1038/nature12345") or None
    """
    # Elsevier PII-based article URLs:
    #   e.g. https://www.jbc.org/article/S0021-9258(19)52451-6/fulltext
    #   DOI = 10.1016/{PII}
    pii_match = re.search(
        r"/article/(S\d{4}-\d{4}\(\d{2}\)\d{5}-\d)(?:/|$)",
        text,
        re.IGNORECASE,
    )
    if pii_match:
        return f"10.1016/{pii_match.group(1)}"

    patterns = [
        r"doi\.org/(10\.\S+)",
        r"(10\.\d{4,}/\S+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip(".,;)")
            # Remove common file extensions and SPIE URL suffixes
            for ext in [
                ".pdf",
                ".html",
                ".htm",
                ".xml",
                ".short",
                ".full",
                ".abstract",
                ".long",
            ]:
                if doi.lower().endswith(ext):
                    doi = doi[: -len(ext)]
            return doi
    return None


def extract_doi_from_pdf(url: str) -> Optional[str]:
    """
    Extract DOI from PDF file by downloading first pages and searching.

    Args:
        url: URL to PDF file

    Returns:
        DOI string or None
    """
    try:
        headers = {**DEFAULT_HEADERS, "Range": f"bytes=0-{PDF_DOWNLOAD_SIZE}"}
        response = requests.get(
            url,
            headers=headers,
            timeout=PDF_DOWNLOAD_TIMEOUT,
            allow_redirects=True,
        )

        content = response.content.decode("latin-1", errors="ignore")

        found_dois = []
        for pattern in DOI_PATTERNS:
            matches = re.finditer(
                pattern, content, re.IGNORECASE | re.MULTILINE
            )
            for match in matches:
                if pattern.startswith(r"s\d"):  # Nature short format
                    doi = f"10.1038/{match.group(0)}"
                else:
                    doi = match.group(1)

                # Cleanup
                doi = re.sub(r'[<>"\'\s].*$', "", doi)
                doi = doi.rstrip(".,;)\\]>}")

                # Validate DOI format
                if re.match(r"10\.\d{4,9}/[A-Za-z0-9\.\-\(\)_/]+$", doi):
                    found_dois.append(doi)

        if found_dois:
            return found_dois[0]

        return None
    except Exception as e:
        print(f"Error extracting DOI from PDF: {e}")
        return None


def extract_optica_info(url: str) -> Optional[dict]:
    """
    Extract journal/volume/issue/page from Optica URLs.

    Args:
        url: Optica URL (e.g., opg.optica.org/oe/fulltext.cfm?uri=oe-29-18-28217)

    Returns:
        Dict with journal, volume, issue, page or None
    """
    uri_match = re.search(r"uri=(\w+)-(\d+)-(\d+)-(\d+)", url)
    if uri_match:
        journal_code = uri_match.group(1)
        volume = uri_match.group(2)
        issue = uri_match.group(3)
        page = uri_match.group(4)

        journal = OPTICA_JOURNALS.get(journal_code.lower(), "Optics")

        return {
            "journal": journal,
            "volume": volume,
            "issue": issue,
            "page": page,
        }
    return None


def extract_ieee_metadata(url: str) -> Optional[dict]:
    """
    Extract DOI and title from an IEEE Xplore URL.

    IEEE's document pages are JS-rendered behind a WAF, so we use the
    articleDetails.jsp endpoint which returns a crawlable HTML page.

    Args:
        url: ieeexplore.ieee.org URL

    Returns:
        Dict with 'doi' and 'title', or None if not an IEEE URL / request fails
    """
    m = re.search(r"ieeexplore\.ieee\.org/(?:abstract/)?document/(\d+)", url, re.IGNORECASE)
    if not m:
        return None
    arnumber = m.group(1)
    try:
        details_url = f"https://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber={arnumber}"
        resp = requests.get(details_url, headers=DEFAULT_HEADERS, timeout=URL_FETCH_TIMEOUT)
        resp.raise_for_status()
        doi_m = re.search(r'"doi"\s*:\s*"(10\.[^"]+)"', resp.text)
        doi = doi_m.group(1).strip() if doi_m else None
        title_m = re.search(r'"title"\s*:\s*"([^"]{10,})"', resp.text)
        title = title_m.group(1) if title_m else None
        if doi or title:
            return {"doi": doi, "title": title}
    except Exception:
        pass
    return None


def extract_metadata_from_url(url: str) -> dict:
    """
    Extract DOI and title from a publisher webpage.

    Args:
        url: Publisher webpage URL

    Returns:
        Dict with 'doi', 'title', and optionally 'optica_info'
    """
    metadata = {"doi": None, "title": None}

    if url.lower().endswith(".pdf"):
        return metadata

    # IEEE Xplore: JS-rendered, use their REST API instead
    if "ieeexplore.ieee.org" in url.lower():
        ieee_meta = extract_ieee_metadata(url)
        if ieee_meta:
            metadata["doi"] = ieee_meta.get("doi")
            metadata["title"] = ieee_meta.get("title")
        return metadata

    # Check for Optica URLs
    if "optica.org" in url.lower() or "osa.org" in url.lower():
        optica_info = extract_optica_info(url)
        if optica_info:
            metadata["optica_info"] = optica_info
            return metadata

    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=URL_FETCH_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract DOI from meta tags
        doi_meta = soup.find("meta", attrs={"name": "citation_doi"})
        if doi_meta:
            metadata["doi"] = doi_meta.get("content")
        else:
            doi_meta = soup.find("meta", attrs={"name": "dc.identifier"})
            if doi_meta and "doi" in doi_meta.get("content", "").lower():
                doi_content = doi_meta.get("content")
                doi_match = re.search(r"10\.\d{4,}/[^\s]+", doi_content)
                if doi_match:
                    metadata["doi"] = doi_match.group(0)

        # Extract title from meta tags
        title_meta = soup.find("meta", attrs={"name": "citation_title"})
        if title_meta:
            metadata["title"] = title_meta.get("content")
        else:
            title_meta = soup.find("meta", attrs={"property": "og:title"})
            if title_meta:
                metadata["title"] = title_meta.get("content")
            else:
                title_tag = soup.find("title")
                if title_tag:
                    metadata["title"] = title_tag.get_text().strip()

        # Fallback: search page text for DOI
        if not metadata["doi"]:
            page_text = soup.get_text()
            doi_match = re.search(r'10\.\d{4,}/[^\s<>"]+', page_text)
            if doi_match:
                metadata["doi"] = doi_match.group(0).rstrip(".,;)")

    except Exception as e:
        print(f"Could not fetch metadata from URL: {e}")

    return metadata
