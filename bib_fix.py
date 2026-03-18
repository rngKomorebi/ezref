#!/usr/bin/env python3
"""
bib_fix.py — Sort, clean, and enrich a BibTeX file based on citation
order in a .tex file.

Usage:
    python bib_fix.py --tex paper.tex --bib refs.bib
    python bib_fix.py --tex paper.tex --bib refs.bib --out final.bib --no-doi
    python bib_fix.py --tex paper.tex --bib refs.bib --keep-unused

What it does:
  * Extracts all citation keys from the .tex file in first-appearance order
  * Parses the .bib file (skips @comment / @preamble / @string)
  * Reports cited keys missing from the bib and bib entries never cited
  * Writes a cleaned output bib with only used entries in citation order
  * Normalises title fields to double-brace {{...}} format
  * Normalises page ranges: single hyphen -> double dash (1-10 -> 1--10)
  * Optionally looks up missing DOIs via the CrossRef API
"""

import argparse
import re
import sys
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Citation command regex
#
# Matches every \\cite variant found in practice:
#   \\cite  \\citep  \\citet  \\citealt  \\citealp  \\citeauthor  \\citeyear
#   \\nocite  \\footcite  \\autocite  \\parencite  \\textcite  \\fullcite
#   ...and starred forms like \\cite*  \\citep*
# Also handles optional [prenote] and/or [postnote] bracket arguments.
# ---------------------------------------------------------------------------
CITE_RE = re.compile(
    r"\\[a-zA-Z]*cite[a-zA-Z]*\*?"  # any command containing "cite"
    r"(?:\[[^\]]*\]){0,2}"  # optional [bracket] args (0-2)
    r"\{([^}]+)\}",  # {key1, key2, ...}
    re.DOTALL,
)

CROSSREF_URL = "https://api.crossref.org/works"
REQUEST_DELAY = 0.5  # seconds between CrossRef requests


# ---------------------------------------------------------------------------
# Citation key extraction
# ---------------------------------------------------------------------------


def extract_citation_keys(tex_content: str) -> tuple[list[str], set[str]]:
    """Return citation keys in first-appearance order plus a set for lookups.

    Handles all \\cite variants and comma-separated groups.
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for group in CITE_RE.findall(tex_content):
        for key in group.split(","):
            key = key.strip()
            if key and key not in seen:
                ordered.append(key)
                seen.add(key)
    return ordered, seen


# ---------------------------------------------------------------------------
# BibTeX parser
# ---------------------------------------------------------------------------


def parse_bib_file(bib_text: str) -> dict[str, list[str]]:
    """Parse a .bib file into {citation_key: entry_lines}.

    Uses brace-depth tracking to handle multi-line entries and nested
    values.  @comment, @preamble, and @string entries are skipped.
    """
    SKIP_TYPES = {"comment", "preamble", "string"}

    entries: dict[str, list[str]] = {}
    buffer: list[str] = []
    depth: int = 0
    current_key: str | None = None
    skip: bool = False

    for line in bib_text.splitlines(keepends=True):
        stripped = line.strip()

        if not buffer:
            if not stripped.startswith("@"):
                continue
            type_m = re.match(r"@(\w+)\s*[{(]", stripped, re.IGNORECASE)
            entry_type = type_m.group(1).lower() if type_m else ""
            skip = entry_type in SKIP_TYPES

            key_m = re.match(
                r"@\w+\s*[{(]\s*([^,}\s]+)", stripped, re.IGNORECASE
            )
            current_key = key_m.group(1).strip() if key_m else None

            buffer = [line]
            depth = line.count("{") - line.count("}")

            # Single-line entry: depth already balanced — commit immediately
            if depth <= 0:
                if not skip and current_key:
                    entries[current_key] = buffer.copy()
                buffer = []
                current_key = None
                skip = False
        else:
            buffer.append(line)
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                if not skip and current_key:
                    entries[current_key] = buffer.copy()
                buffer = []
                current_key = None
                skip = False

    # Flush any entry that ends at EOF without a trailing newline
    if buffer and not skip and current_key:
        entries[current_key] = buffer.copy()

    return entries


# ---------------------------------------------------------------------------
# Entry normalisation helpers
# ---------------------------------------------------------------------------


def _is_balanced_unit(s: str) -> bool:
    """Return True if s is a single brace-balanced unit {…}.

    The opening brace must not close until the final character.
    """
    if not (s.startswith("{") and s.endswith("}")):
        return False
    depth = 0
    for i, ch in enumerate(s):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i == len(s) - 1
    return False


def _fix_title_value(m: re.Match) -> str:
    """Regex replacement callback: wrap title value in exactly double braces.

    Handles:
      {Single braced}               -> {{Single braced}}
      {{Already double}}            -> {{Already double}}  (no-op)
      "Quoted value"                -> {{Quoted value}}
      {Title with {Acronym} inside} -> {{Title with {Acronym} inside}}
    """
    prefix: str = m.group(1)
    raw: str = m.group(2).strip()

    if raw.startswith('"') and raw.endswith('"'):
        return f"{prefix}{{{{{raw[1:-1]}}}}}"

    if raw.startswith("{") and raw.endswith("}"):
        inner = raw[1:-1]
        if _is_balanced_unit(inner):
            # Already double-braced
            return m.group(0)
        return f"{prefix}{{{{{inner}}}}}"

    return m.group(0)


def normalize_entry(entry_text: str) -> str:
    """Normalise a bib entry string.

    1. Title: wrap in double braces {{...}} to lock capitalisation.
    2. Pages: single hyphen -> double dash  (1-10 -> 1--10).
    """
    # Title normalisation (handles single-braced, double-braced, quoted,
    # multi-line, and titles with one level of nested braces)
    entry_text = re.sub(
        r"(title\s*=\s*)(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\")",
        _fix_title_value,
        entry_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Page range normalisation: digits-digits -> digits--digits
    entry_text = re.sub(
        r"(pages\s*=\s*[{\"']?\s*)(\d+)\s*-(?!-)\s*(\d+)",
        lambda m: f"{m.group(1)}{m.group(2)}--{m.group(3)}",
        entry_text,
        flags=re.IGNORECASE,
    )

    return entry_text


# ---------------------------------------------------------------------------
# Title extraction for DOI lookup
# ---------------------------------------------------------------------------


def extract_title_for_doi(entry_text: str) -> str | None:
    """Return the bare title string suitable for a CrossRef query.

    Uses brace-depth counting rather than regex so that it handles titles
    with arbitrary nesting: {T}, {{T}}, {{Title with {Acronym}}}, etc.
    """
    m = re.search(r"title\s*=\s*", entry_text, re.IGNORECASE)
    if not m:
        return None

    pos = m.end()
    while pos < len(entry_text) and entry_text[pos] in " \t\r\n":
        pos += 1
    if pos >= len(entry_text):
        return None

    if entry_text[pos] == '"':
        end = entry_text.find('"', pos + 1)
        if end == -1:
            return None
        raw = entry_text[pos + 1 : end]
    elif entry_text[pos] == "{":
        depth = 0
        i = pos
        while i < len(entry_text):
            ch = entry_text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        raw = entry_text[pos + 1 : i]
    else:
        return None

    raw = re.sub(r"[{}]", "", raw)
    return re.sub(r"\s+", " ", raw).strip() or None


# ---------------------------------------------------------------------------
# DOI lookup via CrossRef
# ---------------------------------------------------------------------------


def fetch_doi(title: str) -> str | None:
    """Query CrossRef for a DOI by title. Returns DOI string or None."""
    try:
        resp = requests.get(
            CROSSREF_URL,
            params={
                "query.bibliographic": title,
                "rows": 1,
                "select": "DOI,title",
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])
        if items and "DOI" in items[0]:
            return items[0]["DOI"]
    except requests.RequestException as exc:
        print(f"  Warning: CrossRef request failed: {exc}", file=sys.stderr)
    return None


def insert_doi(lines: list[str], doi: str) -> list[str]:
    """Insert  doi = {...},  immediately before the entry's closing brace.

    Also ensures the previously-last field line has a trailing comma,
    because adding a new field after it makes the comma mandatory.
    """
    doi_line = f"  doi = {{{doi}}},\n"
    result = list(lines)
    for i in reversed(range(len(result))):
        if result[i].strip() == "}":
            # Add trailing comma to the preceding field line if missing
            if i > 0:
                prev = result[i - 1]
                stripped_prev = prev.rstrip()
                if stripped_prev and not stripped_prev.endswith(","):
                    result[i - 1] = stripped_prev + ",\n"
            return result[:i] + [doi_line] + result[i:]
    # Fallback: no explicit closing-brace line found
    prev = result[-1]
    stripped_prev = prev.rstrip()
    if stripped_prev and not stripped_prev.endswith(","):
        result[-1] = stripped_prev + ",\n"
    return result[:-1] + [doi_line, lines[-1]]


# ---------------------------------------------------------------------------
# arXiv helpers
# ---------------------------------------------------------------------------

ARXIV_API_URL = "http://export.arxiv.org/api/query"

# Matches new-style (2301.12345) and old-style (hep-ph/0123456) arXiv IDs
ARXIV_ID_RE = re.compile(
    r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+/\d{7}(?:v\d+)?)",
    re.IGNORECASE,
)

# DOI prefixes belonging to preprint servers / open repositories
_PREPRINT_DOI_PREFIXES = frozenset(
    {
        "10.1364/opticaopen",  # Optica Open
        "10.21203",  # Research Square
        "10.26434",  # ChemRxiv
        "10.31219",  # OSF Preprints
        "10.31730",  # ESSOAr
        "10.20944",  # Preprints.org
        "10.36227",  # TechRxiv
        "10.22541",  # Authorea
        "10.2139",  # SSRN
    }
)


def extract_arxiv_id(entry_text: str) -> str | None:
    """Return the arXiv ID from a bib entry, or None if not an arXiv entry.

    Checks (in order): eprint field, arxiv.org URL, inline arXiv:ID pattern.
    """
    # eprint field (most reliable)
    m = re.search(
        r"eprint\s*=\s*[{\"']\s*([^}\"']+?)\s*[}\"']",
        entry_text,
        re.IGNORECASE,
    )
    if m:
        id_m = ARXIV_ID_RE.search(m.group(1))
        if id_m:
            return id_m.group(1)
    # URL containing arxiv.org/abs/
    m = re.search(r"arxiv\.org/abs/([^\s}\"#]+)", entry_text, re.IGNORECASE)
    if m:
        raw = m.group(1).rstrip("/")
        id_m = ARXIV_ID_RE.match(raw)
        if id_m:
            return id_m.group(1)
    # Inline arXiv:ID pattern in any field
    m = re.search(
        r"arXiv\s*[:\s]\s*(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+/\d{7}(?:v\d+)?)",
        entry_text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    return None


def fetch_arxiv_publication(arxiv_id: str) -> dict | None:
    """Query the arXiv API to check if a paper has been published.

    Returns a dict with any of 'doi', 'journal_ref', 'title' when the paper
    has a known publication record, or None if no such record exists.
    """
    import xml.etree.ElementTree as ET

    query_id = re.sub(r"v\d+$", "", arxiv_id)  # strip version suffix
    try:
        resp = requests.get(
            ARXIV_API_URL,
            params={"id_list": query_id, "max_results": 1},
            timeout=10,
        )
        resp.raise_for_status()
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(resp.text)
        atom_entry = root.find("atom:entry", ns)
        if atom_entry is None:
            return None
        result: dict = {}
        for tag, key in [
            ("arxiv:journal_ref", "journal_ref"),
            ("arxiv:doi", "doi"),
        ]:
            elem = atom_entry.find(tag, ns)
            if elem is not None and elem.text:
                result[key] = elem.text.strip()
        title_elem = atom_entry.find("atom:title", ns)
        if title_elem is not None and title_elem.text:
            result["title"] = re.sub(r"\s+", " ", title_elem.text).strip()
        return result if ("journal_ref" in result or "doi" in result) else None
    except (requests.RequestException, ET.ParseError, KeyError, ValueError):
        return None


# CrossRef type → BibTeX entry type
_CR_TYPE_MAP = {
    "journal-article": "article",
    "book-chapter": "incollection",
    "proceedings-article": "inproceedings",
    "monograph": "book",
    "dissertation": "phdthesis",
    "preprint": "article",
}


def _bibtex_from_crossref_metadata(doi: str, new_key: str) -> str | None:
    """Build a BibTeX entry from CrossRef REST API metadata.

    Used as a fallback when DOI content negotiation does not return BibTeX.
    """
    try:
        resp = requests.get(
            f"https://api.crossref.org/works/{requests.utils.quote(doi, safe='')}",
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        work = resp.json().get("message", {})
    except requests.RequestException:
        return None

    entry_type = _CR_TYPE_MAP.get(work.get("type", ""), "misc")
    fields: list[tuple[str, str]] = []

    # Authors
    authors = work.get("author", [])
    if authors:
        parts = []
        for a in authors:
            name = a.get("family", "")
            if a.get("given"):
                name = f"{name}, {a['given']}"
            parts.append(name)
        fields.append(("author", " and ".join(parts)))

    # Title
    titles = work.get("title", [])
    if titles:
        fields.append(("title", f"{{{titles[0]}}}"))

    # Container (journal / book title)
    container = work.get("container-title", [])
    if container:
        key = "journal" if entry_type == "article" else "booktitle"
        fields.append((key, container[0]))

    # Publisher
    if work.get("publisher"):
        fields.append(("publisher", work["publisher"]))

    # Year (prefer published, fall back to issued)
    for date_key in ("published", "issued", "created"):
        dp = (work.get(date_key) or {}).get("date-parts", [[]])
        if dp and dp[0]:
            fields.append(("year", str(dp[0][0])))
            if len(dp[0]) >= 2:
                import calendar

                fields.append(("month", calendar.month_abbr[dp[0][1]].lower()))
            break

    if work.get("volume"):
        fields.append(("volume", work["volume"]))
    if work.get("issue"):
        fields.append(("number", work["issue"]))
    if work.get("page"):
        fields.append(("pages", work["page"].replace("-", "--")))
    if work.get("ISSN"):
        fields.append(("issn", work["ISSN"][0]))
    if work.get("URL"):
        fields.append(("url", work["URL"]))
    fields.append(("doi", doi))

    lines = [f"@{entry_type}{{{new_key},\n"]
    for k, v in fields:
        lines.append(f"  {k} = {{{v}}},\n")
    lines.append("}\n")
    return "".join(lines)


def _extract_surnames(bib_text: str) -> set[str]:
    """Return a set of lowercased author surnames from a bib entry string."""
    m = re.search(
        r"author\s*=\s*[{\"](.*?)[}\"]",
        bib_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return set()
    raw = re.sub(r"[{}]", "", m.group(1))
    surnames: set[str] = set()
    for person in re.split(r"\band\b", raw, flags=re.IGNORECASE):
        person = person.strip()
        if not person:
            continue
        # "Family, Given" or "Given Family" — take the first token before comma
        # or the last token if no comma
        if "," in person:
            surnames.add(person.split(",")[0].strip().lower())
        else:
            surnames.add(person.split()[-1].strip().lower())
    return surnames


def _is_preprint_entry(bibtex_text: str, doi: str = "") -> bool:
    """Return True if a BibTeX entry is from a known preprint server.

    Checks the DOI prefix and the journal/booktitle field value.
    """
    if doi and any(doi.lower().startswith(p) for p in _PREPRINT_DOI_PREFIXES):
        return True
    journal_m = re.search(
        r"(?:journal|booktitle)\s*=\s*[{\"](.*?)[}\"]",
        bibtex_text,
        re.IGNORECASE | re.DOTALL,
    )
    if journal_m:
        jname = journal_m.group(1).lower()
        if any(
            p in jname
            for p in (
                "optica open",
                "biorxiv",
                "medrxiv",
                "chemrxiv",
                "ssrn",
                "research square",
                "preprints.org",
                "techrxiv",
                "authorea",
                "opticaopen",
            )
        ):
            return True
    return False


def fetch_doi_for_arxiv(entry_text: str) -> str | None:
    """Search CrossRef for a published (non-preprint) DOI for an arXiv entry.

    Combines title + author surnames in the query, checks up to 5 results,
    and skips any whose CrossRef type is ``posted-content``, whose DOI
    belongs to a known preprint server, or whose authors don't overlap with
    the source entry.  Returns the best-matching DOI or None.
    """
    title = extract_title_for_doi(entry_text)
    if not title:
        return None
    source_surnames = _extract_surnames(entry_text)
    author_hint = (
        " ".join(list(source_surnames)[:3]) if source_surnames else ""
    )
    query = f"{title} {author_hint}".strip()

    try:
        resp = requests.get(
            CROSSREF_URL,
            params={
                "query.bibliographic": query,
                "rows": 5,
                "select": "DOI,title,author,type",
            },
            timeout=10,
        )
        resp.raise_for_status()
        for item in resp.json().get("message", {}).get("items", []):
            if "DOI" not in item:
                continue
            # Skip preprints by CrossRef type or DOI prefix
            if item.get("type") == "posted-content":
                continue
            if any(
                item["DOI"].lower().startswith(p)
                for p in _PREPRINT_DOI_PREFIXES
            ):
                continue
            # Skip if no author overlap with the source
            if source_surnames:
                cr_surnames = {
                    a.get("family", "").lower()
                    for a in item.get("author", [])
                    if a.get("family")
                }
                if cr_surnames and not (source_surnames & cr_surnames):
                    continue
            return item["DOI"]
    except requests.RequestException as exc:
        print(f"  Warning: CrossRef request failed: {exc}", file=sys.stderr)
    return None


def fetch_bibtex_from_doi(
    doi: str,
    new_key: str,
    source_entry: str | None = None,
) -> str | None:
    """Fetch a BibTeX entry for *doi* and assign *new_key* as the cite key.

    Strategy:
    1. DOI content negotiation (``Accept: application/x-bibtex``) — fast,
       supported by most major publishers.
    2. CrossRef REST API fallback — constructs BibTeX from metadata; works
       for publishers / repositories that don't serve BibTeX directly.

    If *source_entry* is given (the original arXiv bib text), the fetched
    entry is rejected unless it shares at least one author surname, guarding
    against DOIs that resolve to a completely different paper.
    """
    source_surnames = (
        _extract_surnames(source_entry) if source_entry else set()
    )

    def _valid(text: str) -> bool:
        """Return True if text passes all validity checks."""
        if not text.startswith("@"):
            return False
        if _is_preprint_entry(text, doi):
            return False  # preprint server — not a published version
        if source_surnames:
            fetched_surnames = _extract_surnames(text)
            if fetched_surnames and not (source_surnames & fetched_surnames):
                return False  # no surname overlap — likely a wrong paper
        return True

    # ── 1. Content negotiation ───────────────────────────────────────────────
    try:
        resp = requests.get(
            f"https://doi.org/{doi}",
            headers={"Accept": "application/x-bibtex"},
            timeout=10,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            text = resp.text.strip()
            if _valid(text):
                text = re.sub(
                    r"(@\w+\s*\{)\s*[^,\s]+",
                    lambda m: f"{m.group(1)}{new_key}",
                    text,
                    count=1,
                )
                return text
    except requests.RequestException:
        pass

    # ── 2. CrossRef metadata fallback ────────────────────────────────────────
    text = _bibtex_from_crossref_metadata(doi, new_key)
    if text and _valid(text):
        return text
    return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sort, clean, and enrich a .bib file based on citation order "
            "in a .tex file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tex", required=True, metavar="FILE", help="Input .tex source file"
    )
    parser.add_argument(
        "--bib", required=True, metavar="FILE", help="Input .bib file"
    )
    parser.add_argument(
        "--out",
        metavar="FILE",
        help="Output path (default: <bib_stem>_clean.bib beside the bib)",
    )
    parser.add_argument(
        "--no-doi", action="store_true", help="Skip DOI lookup via CrossRef"
    )
    parser.add_argument(
        "--keep-unused",
        action="store_true",
        help="Append unused bib entries at the end of the output",
    )
    args = parser.parse_args()

    tex_path = Path(args.tex)
    bib_path = Path(args.bib)
    out_path = (
        Path(args.out)
        if args.out
        else bib_path.with_name(bib_path.stem + "_clean.bib")
    )

    if not tex_path.exists():
        sys.exit(f"Error: .tex file not found: {tex_path}")
    if not bib_path.exists():
        sys.exit(f"Error: .bib file not found: {bib_path}")

    tex_content = tex_path.read_text(encoding="utf-8")
    bib_content = bib_path.read_text(encoding="utf-8")

    used_ordered, used_set = extract_citation_keys(tex_content)
    print(f"📄  {len(used_ordered)} unique citation keys in '{tex_path.name}'")

    bib_entries = parse_bib_file(bib_content)
    print(f"📚  {len(bib_entries)} entries parsed from '{bib_path.name}'")

    bib_keys = set(bib_entries)
    unused = sorted(bib_keys - used_set)
    missing = sorted(used_set - bib_keys)

    if unused:
        label = "entry" if len(unused) == 1 else "entries"
        print(
            f"\n📋  {len(unused)} unused bib {label} "
            f"(in .bib but never cited):"
        )
        for k in unused:
            print(f"     - {k}")

    if missing:
        label = "key" if len(missing) == 1 else "keys"
        print(f"\n⚠️   {len(missing)} cited {label} not found in bib file:")
        for k in missing:
            print(f"     - {k}")

    out_keys = list(used_ordered)
    if args.keep_unused:
        out_keys += [k for k in unused if k in bib_entries]

    doi_added = 0
    written = 0

    with out_path.open("w", encoding="utf-8") as f:
        for key in out_keys:
            if key not in bib_entries:
                continue

            entry_text = normalize_entry("".join(bib_entries[key]))
            lines = entry_text.splitlines(keepends=True)

            if not args.no_doi:
                has_doi = re.search(
                    r"^\s*doi\s*=", entry_text, re.IGNORECASE | re.MULTILINE
                )
                if not has_doi:
                    title = extract_title_for_doi(entry_text)
                    if title:
                        print(f"  🔍  '{key}' ... ", end="", flush=True)
                        doi = fetch_doi(title)
                        time.sleep(REQUEST_DELAY)
                        if doi:
                            lines = insert_doi(lines, doi)
                            doi_added += 1
                            print(doi)
                        else:
                            print("not found")

            f.writelines(lines)
            f.write("\n")
            written += 1

    print(f"\n✅  Wrote {written} entries -> '{out_path}'")
    if not args.no_doi:
        print(f"   🔗  DOIs added: {doi_added}")


if __name__ == "__main__":
    main()
