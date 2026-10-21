"""Citation formatters for various academic styles.

Author-count rules (reference-list entries):
- APA 7:        up to 20 authors; 21+ -> first 19, ". . .", last author.
- MLA 9:        1-2 authors; 3+ -> first author, et al.
- Chicago 18:   up to 6 authors; 7+ -> first 3, et al.
- IEEE:         up to 6 authors; 7+ -> first author et al.
- Harvard:      (Cite Them Right) up to 3 authors; 4+ -> first author et al.
- Vancouver:    (ICMJE/NLM) up to 6 authors; 7+ -> first 6, et al.
- Nature:       up to 5 authors; 6+ -> first author et al.
- Komorebi:     up to 10 authors; 11+ -> first author et al.

Typography: every formatter returns plain text by default; pass html=True to
get <i>/<b> markup (journal titles italic; APA volume italic; Nature and
Komorebi volume bold). Nature style also covers Nature Communications.
"""

import html as _html
import re

_RANGE = re.compile(r"^\s*(\d+)\s*(?:-+|–|—)\s*(\d+)\s*$")

# Private-use sentinels marking italic / bold spans until rendering
_IT_OPEN, _IT_CLOSE, _BF_OPEN, _BF_CLOSE = "", "", "", ""


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────


def _it(text: str) -> str:
    return f"{_IT_OPEN}{text}{_IT_CLOSE}" if text else text


def _bf(text: str) -> str:
    return f"{_BF_OPEN}{text}{_BF_CLOSE}" if text else text


def _render(citation: str, html: bool) -> str:
    """Resolve italic/bold sentinels to HTML tags, or strip them for plain text."""
    if not html:
        return re.sub(f"[{_IT_OPEN}{_IT_CLOSE}{_BF_OPEN}{_BF_CLOSE}]", "", citation)
    out = _html.escape(citation, quote=False)
    for mark, tag in (
        (_IT_OPEN, "<i>"),
        (_IT_CLOSE, "</i>"),
        (_BF_OPEN, "<b>"),
        (_BF_CLOSE, "</b>"),
        ("\n", "<br>"),
    ):
        out = out.replace(mark, tag)
    return out


def _split_authors(authors: str) -> list[tuple[str, str]]:
    """Split a BibTeX author string into (last, first) pairs."""
    names = []
    for author in re.split(r"\s+and\s+", authors.strip()):
        author = author.strip()
        if not author:
            continue
        if author.startswith("{") and author.endswith("}"):
            # Braced corporate author, e.g. {CMS Collaboration}
            names.append((author[1:-1].strip(), ""))
        elif "," in author:
            last, first = author.split(",", 1)
            names.append((last.strip(), first.strip()))
        else:
            parts = author.split()
            names.append((parts[-1], " ".join(parts[:-1])))
    return [(last.replace("{", "").replace("}", ""), first) for last, first in names]


def _initials(first: str, dots: bool = True) -> str:
    """'John Ronald' -> 'J. R.'; 'Jean-Pierre' -> 'J.-P.' ('JP' without dots)."""
    words = []
    for word in first.replace(".", ". ").split():
        letters = []
        for part in word.split("-"):
            m = re.search(r"[^\W\d_]", part)
            if m:
                letters.append(m.group(0).upper() + ("." if dots else ""))
        if letters:
            words.append(("-" if dots else "").join(letters))
    return (" " if dots else "").join(words)


def _last_initials(last: str, first: str) -> str:
    """'Smith, J. R.' (APA, Harvard, Nature)."""
    initials = _initials(first)
    return f"{last}, {initials}" if initials else last


def _initials_last(last: str, first: str) -> str:
    """'J. R. Smith' (IEEE, Komorebi)."""
    initials = _initials(first)
    return f"{initials} {last}" if initials else last


def _full_name(last: str, first: str, inverted: bool) -> str:
    """'Smith, John' if inverted else 'John Smith' (MLA, Chicago)."""
    if not first:
        return last
    return f"{last}, {first}" if inverted else f"{first} {last}"


def _end(text: str, punct: str = ".") -> str:
    """Append punctuation unless the text already ends with a terminal mark."""
    text = text.rstrip()
    return text if text.endswith((".", "?", "!")) else text + punct


def _title(entry: dict) -> str:
    return entry.get("title", "").replace("{", "").replace("}", "").strip()


def _year(entry: dict) -> str:
    return entry.get("year") or "n.d."


def _venue(entry: dict) -> str:
    return entry.get("journal") or entry.get("booktitle") or ""


def _changed_digits(start: str, end: str, keep: int) -> str:
    """Drop the leading digits `end` shares with `start`, keeping at least `keep`."""
    if len(start) != len(end) or int(end) <= int(start):
        return end
    i = 0
    while i < len(end) - keep and start[i] == end[i]:
        i += 1
    return end[i:]


def _pages(entry: dict, dash: str = "–", elide=None) -> str:
    """Page range with the style's dash; `elide(start, end)` shortens the end."""
    pages = (entry.get("pages") or "").strip()
    if not pages:
        return ""
    m = _RANGE.match(pages)
    if not m:
        return re.sub(r"\s*(?:-+|–|—)\s*", dash, pages)
    start, end = m.groups()
    if elide:
        end = elide(start, end)
    return f"{start}{dash}{end}"


def _is_range(pages: str) -> bool:
    return bool(re.search(r"[-–]", pages))


def _mla_elide(start: str, end: str) -> str:
    # MLA: second number gives only the last two digits unless more are needed
    return end if int(start) < 100 else _changed_digits(start, end, 2)


def _chicago_elide(start: str, end: str) -> str:
    # CMOS 9.64: full below 100 and at multiples of 100; 101-109 changed
    # part only; otherwise at least two digits
    s = int(start)
    if s < 100 or s % 100 == 0:
        return end
    return _changed_digits(start, end, 1 if s % 100 < 10 else 2)


def _nlm_elide(start: str, end: str) -> str:
    # NLM/Vancouver: drop all repeated leading digits, e.g. 284-7
    return _changed_digits(start, end, 1)


def _doi(entry: dict) -> str:
    """Bare DOI (10.xxxx/...), or '' if the field holds no real DOI."""
    doi = (entry.get("doi") or "").strip()
    doi = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    return doi if doi.startswith("10.") else ""


def _link(entry: dict) -> str:
    """DOI as a URL, else the entry's own URL (e.g. arXiv abstract page)."""
    doi = _doi(entry)
    if doi:
        return f"https://doi.org/{doi}"
    for key in ("url", "doi"):
        value = (entry.get(key) or "").strip()
        if value.startswith("http"):
            return value
    return ""


def _names(entry: dict) -> list[tuple[str, str]]:
    return _split_authors(entry.get("author") or "Unknown") or [("Unknown", "")]


# ─────────────────────────────────────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────────────────────────────────────


def format_apa_citation(entry: dict, html: bool = False) -> str:
    """Format citation in APA 7th edition style."""
    names = [_last_initials(last, first) for last, first in _names(entry)]
    if len(names) == 1:
        author_str = names[0]
    elif len(names) <= 20:
        author_str = ", ".join(names[:-1]) + ", & " + names[-1]
    else:
        author_str = ", ".join(names[:19]) + ", . . . " + names[-1]

    venue = _venue(entry)
    title = _end(_title(entry))
    # Standalone works (no container) take an italic title
    citation = f"{author_str} ({_year(entry)}). {title if venue else _it(title)}"

    if venue:
        citation += f" {_it(venue)}"
        if entry.get("volume"):
            citation += f", {_it(entry['volume'])}"
            if entry.get("number"):
                citation += f"({entry['number']})"
        pages = _pages(entry)
        if pages:
            citation += f", {pages}"
        citation += "."

    link = _link(entry)
    if link:
        citation += f" {link}"

    return _render(citation, html)


def format_mla_citation(entry: dict, html: bool = False) -> str:
    """Format citation in MLA 9th edition style."""
    names = _names(entry)
    first_author = _full_name(*names[0], inverted=True)
    if len(names) == 1:
        mla_author = first_author
    elif len(names) == 2:
        mla_author = f"{first_author}, and {_full_name(*names[1], inverted=False)}"
    else:
        mla_author = f"{first_author}, et al."

    citation = f'{_end(mla_author)} "{_end(_title(entry))}"'

    parts = []
    venue = _venue(entry)
    if venue:
        parts.append(_it(venue))
    if entry.get("volume"):
        parts.append(f"vol. {entry['volume']}")
    if entry.get("number"):
        parts.append(f"no. {entry['number']}")
    parts.append(_year(entry))
    pages = _pages(entry, elide=_mla_elide)
    if pages:
        parts.append(f"{'pp.' if _is_range(pages) else 'p.'} {pages}")
    citation += " " + ", ".join(parts) + "."

    link = _link(entry)
    if link:
        citation += f" {link}."

    return _render(citation, html)


def format_chicago_citation(entry: dict, html: bool = False) -> str:
    """Format citation in Chicago 18th edition (notes-bibliography) style."""
    names = _names(entry)
    full = [_full_name(*names[0], inverted=True)] + [
        _full_name(*n, inverted=False) for n in names[1:]
    ]
    if len(full) == 1:
        author_str = full[0]
    elif len(full) <= 6:
        author_str = ", ".join(full[:-1]) + ", and " + full[-1]
    else:
        author_str = ", ".join(full[:3]) + ", et al."

    citation = f'{_end(author_str)} "{_end(_title(entry))}"'

    venue = _venue(entry)
    if venue:
        citation += f" {_it(venue)}"
        if entry.get("volume"):
            citation += f" {entry['volume']}"
        if entry.get("number"):
            citation += f", no. {entry['number']}"
        citation += f" ({_year(entry)})"
        pages = _pages(entry, elide=_chicago_elide)
        if pages:
            citation += f": {pages}"
        citation += "."
    else:
        citation += f" {_year(entry)}."

    link = _link(entry)
    if link:
        citation += f" {link}."

    return _render(citation, html)


def format_ieee_citation(entry: dict, html: bool = False) -> str:
    """Format citation in IEEE style."""
    names = [_initials_last(last, first) for last, first in _names(entry)]
    if len(names) > 6:
        author_str = f"{names[0]} et al."
    elif len(names) == 1:
        author_str = names[0]
    elif len(names) == 2:
        author_str = f"{names[0]} and {names[1]}"
    else:
        author_str = ", ".join(names[:-1]) + ", and " + names[-1]

    citation = f'{author_str}, "{_title(entry)},"'

    parts = []
    venue = _venue(entry)
    if venue:
        parts.append(_it(venue))
        if entry.get("volume"):
            parts.append(f"vol. {entry['volume']}")
        if entry.get("number"):
            parts.append(f"no. {entry['number']}")
        pages = _pages(entry)
        if pages:
            parts.append(f"{'pp.' if _is_range(pages) else 'p.'} {pages}")
    parts.append(_year(entry))
    doi = _doi(entry)
    if doi:
        parts.append(f"doi: {doi}")
    citation += " " + ", ".join(parts) + "."

    if not doi and _link(entry):
        citation += f" [Online]. Available: {_link(entry)}"

    return _render(citation, html)


def format_harvard_citation(entry: dict, html: bool = False) -> str:
    """Format citation in Harvard (Cite Them Right) style."""
    names = [_last_initials(last, first) for last, first in _names(entry)]
    if len(names) >= 4:
        author_str = f"{names[0]} et al."
    elif len(names) == 1:
        author_str = names[0]
    else:
        author_str = ", ".join(names[:-1]) + " and " + names[-1]

    citation = f"{author_str} ({_year(entry)}) '{_title(entry)}'"

    venue = _venue(entry)
    if venue:
        citation += f", {_it(venue)}"
        if entry.get("volume"):
            citation += f", {entry['volume']}"
            if entry.get("number"):
                citation += f"({entry['number']})"
        pages = _pages(entry)
        if pages:
            citation += f", {'pp.' if _is_range(pages) else 'p.'} {pages}"
    citation += "."

    link = _link(entry)
    if link:
        citation += f" Available at: {link}."

    return _render(citation, html)


def format_vancouver_citation(entry: dict, html: bool = False) -> str:
    """Format citation in Vancouver (ICMJE / NLM) style."""
    names = []
    for last, first in _names(entry):
        initials = _initials(first, dots=False)
        names.append(f"{last} {initials}" if initials else last)
    if len(names) > 6:
        author_str = ", ".join(names[:6]) + ", et al"
    else:
        author_str = ", ".join(names)

    citation = f"{_end(author_str)} {_end(_title(entry))}"

    venue = _venue(entry)
    if venue:
        citation += f" {_end(venue)} {_year(entry)}"
        if entry.get("volume"):
            citation += f";{entry['volume']}"
        if entry.get("number"):
            citation += f"({entry['number']})"
        pages = _pages(entry, dash="-", elide=_nlm_elide)
        if pages:
            citation += f":{pages}"
        citation += "."
    else:
        citation += f" {_year(entry)}."

    doi = _doi(entry)
    if doi:
        citation += f" doi: {doi}"
    elif _link(entry):
        citation += f" Available from: {_link(entry)}"

    return _render(citation, html)


def format_komorebi_citation(entry: dict, html: bool = False) -> str:
    """Format citation in Komorebi style (all authors up to 10, else first et al.)."""
    names = [_initials_last(last, first) for last, first in _names(entry)]
    if len(names) > 10:
        author_str = f"{names[0]} et al."
    elif len(names) > 1:
        author_str = ", ".join(names[:-1]) + " and " + names[-1]
    else:
        author_str = names[0]

    title = _title(entry)
    year = _year(entry)
    eprint = entry.get("eprint", "")

    citation = f"{author_str}, {title},"

    venue = _venue(entry)
    if venue:
        pages = _pages(entry)

        citation += f" {_it(venue)}"
        if entry.get("volume"):
            citation += f" {_bf(entry['volume'])}"
        citation += f" ({year})"
        if pages:
            citation += f" {pages}"
        if eprint:
            citation += f" [arXiv:{eprint}]"
        citation += "."
    else:
        if eprint:
            citation += f" arXiv:{eprint} ({year})."
        else:
            citation += f" ({year})."

    link = _link(entry)
    if link:
        citation += f"\n{link}"

    return _render(citation, html)


def format_nature_citation(entry: dict, html: bool = False) -> str:
    """Format citation in Nature / Nature Communications style."""
    names = [_last_initials(last, first) for last, first in _names(entry)]
    if len(names) > 5:
        author_str = f"{names[0]} et al."
    elif len(names) > 1:
        author_str = ", ".join(names[:-1]) + " & " + names[-1]
    else:
        author_str = names[0]

    citation = f"{_end(author_str)} {_end(_title(entry))}"

    venue = _venue(entry)
    if venue:
        citation += f" {_it(venue)}"
        if entry.get("volume"):
            citation += f" {_bf(entry['volume'])}"
        pages = _pages(entry)
        if pages:
            citation += f", {pages}"
    elif _link(entry):
        citation += f" Preprint at {_link(entry)}"
    citation += f" ({_year(entry)})."

    return _render(citation, html)
