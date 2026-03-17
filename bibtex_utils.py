"""BibTeX utilities for creating and formatting entries."""

import re
from typing import Optional

import requests

from config import BIBTEX_FIELD_ORDER, CROSSREF_TYPE_MAP


def normalize_author_string(author_str: str) -> str:
    """Normalize author names to Title Case and standard BibTeX format."""
    authors = [
        a.strip()
        for a in re.split(r"\s+and\s+", author_str, flags=re.IGNORECASE)
    ]
    normalized = []
    for author in authors:
        parts = [p.strip() for p in author.split(",", 1)]
        if len(parts) == 2:
            last, first = parts
        else:
            # Fallback if no comma
            first_last = parts[0].split()
            last = first_last[-1]
            first = " ".join(first_last[:-1])
        norm = f"{last.title()}, {first.title()}"
        normalized.append(norm)
    return " and ".join(normalized)


def format_arxiv_authors(author_list: list[dict]) -> str:
    """Convert arXiv author list to BibTeX format."""
    formatted = []
    for author in author_list:
        full_name = author["name"]
        parts = full_name.strip().split()
        if len(parts) >= 2:
            first = " ".join(parts[:-1])
            last = parts[-1]
            formatted.append(f"{last}, {first}")
        else:
            formatted.append(full_name)
    return " and ".join(formatted)


def make_bib_key(author_str: str, year: str) -> str:
    """Generate an AuthorYear BibTeX key, e.g. 'Smith2023'."""
    if not author_str:
        return f"Unknown{year or ''}"
    first_author = author_str.split(" and ")[0]
    if "," in first_author:
        last_name = first_author.split(",")[0].strip()
    else:
        parts = first_author.strip().split()
        last_name = parts[-1] if parts else "Unknown"
    last_name = re.sub(r"[^a-zA-Z]", "", last_name)
    last_name = last_name.title() if last_name else "Unknown"
    return f"{last_name}{year or ''}"


def make_bib_entry_from_arxiv(item: dict) -> dict:
    """
    Create BibTeX entry dict from arXiv API response.

    Args:
        item: arXiv entry dict from feedparser

    Returns:
        BibTeX entry dict
    """
    entry_id = item.get("id").split("/")[-1]
    entry_authors = format_arxiv_authors(item.get("authors", []))
    entry_title = item.get("title")
    entry_year = item.get("published").split("-")[0]
    entry_month = item.get("published").split("-")[1]

    # Get arXiv ID without version
    arxiv_id = entry_id.replace("v", "").split("v")[0]
    entry_url = f"https://arxiv.org/abs/{arxiv_id}"
    pdf_link = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    # Check links for PDF URL
    for link in item.get("links", []):
        if link.get("type") == "application/pdf":
            pdf_link = link.get("href", pdf_link)
            break

    return {
        "ENTRYTYPE": "article",
        "ID": make_bib_key(entry_authors, entry_year),
        "author": entry_authors,
        "title": f"{{{entry_title}}}",
        "year": entry_year if entry_year else "",
        "month": entry_month if entry_month else "",
        "doi": entry_url if entry_url else "",
        "url": entry_url,
        "pdf_url": pdf_link,
    }


def make_bib_entry_from_crossref(item: dict) -> dict:
    """
    Create BibTeX entry dict from CrossRef API response.

    Args:
        item: CrossRef item dict

    Returns:
        BibTeX entry dict
    """
    # Map CrossRef type to BibTeX entry type
    crossref_type = item.get("type", "").lower()
    entry_type = CROSSREF_TYPE_MAP.get(crossref_type, "misc")

    # Format authors
    authors = item.get("author", [])
    raw_author_str = " and ".join(
        f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
        for a in authors
    )
    author_str = normalize_author_string(raw_author_str)

    # Extract year
    year = item.get("issued", {}).get("date-parts", [[None]])[0][0]

    # Extract fields
    title = item.get("title", [""])[0]
    container_title = item.get("container-title", [""])[0]
    volume = str(item.get("volume", ""))
    number = str(item.get("issue", ""))
    pages = item.get("page", "")
    doi = item.get("DOI", "")
    publisher = item.get("publisher", "")

    # Build entry dict
    entry = {
        "ENTRYTYPE": entry_type,
        "ID": make_bib_key(author_str, str(year) if year else ""),
        "author": author_str,
        "title": f"{{{title}}}",
        "year": str(year) if year else "",
        "doi": doi,
    }

    # Check for publisher PDF (open access)
    pdf_url = _check_publisher_pdf(item)
    if pdf_url:
        entry["pdf_url"] = pdf_url

    if publisher:
        entry["publisher"] = publisher

    # Add type-specific fields
    if entry_type == "article":
        entry["journal"] = container_title
        if volume:
            entry["volume"] = volume
        if number:
            entry["number"] = number
        if pages:
            entry["pages"] = pages
    elif entry_type == "inproceedings":
        entry["booktitle"] = container_title
        if pages:
            entry["pages"] = pages
    elif entry_type == "book":
        if publisher:
            entry["publisher"] = publisher
    elif entry_type == "incollection":
        entry["booktitle"] = container_title
        if pages:
            entry["pages"] = pages

    return entry


def _check_publisher_pdf(item: dict) -> Optional[str]:
    """Check if CrossRef item has accessible publisher PDF."""
    for link in item.get("link", []):
        if link.get("content-type") in ["application/pdf", "unspecified"]:
            candidate_url = link.get("URL")
            if candidate_url:
                try:
                    headers = {"Range": "bytes=0-1024"}
                    response = requests.get(
                        candidate_url,
                        headers=headers,
                        timeout=3,
                        allow_redirects=True,
                    )
                    if response.status_code in [
                        200,
                        206,
                    ] and response.headers.get("content-type", "").startswith(
                        "application/pdf"
                    ):
                        return candidate_url
                except Exception:
                    continue
    return None


def bib_entry_dict_to_string(entry: dict) -> str:
    """
    Convert BibTeX entry dict to formatted string.

    Args:
        entry: BibTeX entry dict with ENTRYTYPE, ID, and field keys

    Returns:
        Formatted BibTeX string
    """
    lines = [f"@{entry['ENTRYTYPE']}{{{entry['ID']},"]

    # Add fields in preferred order
    for key in BIBTEX_FIELD_ORDER:
        if key in entry and entry[key]:
            lines.append(f"  {key} = {{{entry[key]}}},")

    # Add any remaining fields not in the order list
    for key in entry:
        if key not in {"ENTRYTYPE", "ID"} and key not in BIBTEX_FIELD_ORDER:
            if entry[key]:
                lines.append(f"  {key} = {{{entry[key]}}},")

    # Remove trailing comma from last field
    if len(lines) > 1:
        lines[-1] = lines[-1].rstrip(",")

    lines.append("}")
    return "\n".join(lines)
