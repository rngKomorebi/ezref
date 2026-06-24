"""Citation formatters for various academic styles."""


def format_apa_citation(entry: dict) -> str:
    """Format citation in APA style."""
    authors = entry.get("author", "Unknown")
    year = entry.get("year", "n.d.")
    title = entry.get("title", "").strip("{}")

    citation = f"{authors} ({year}). {title}."

    venue = entry.get("journal") or entry.get("booktitle")
    if venue:
        journal = venue
        citation += f" {journal}"
        if "volume" in entry and entry["volume"]:
            citation += f", {entry['volume']}"
        if "number" in entry and entry["number"]:
            citation += f"({entry['number']})"
        if "pages" in entry and entry["pages"]:
            citation += f", {entry['pages']}"
        citation += "."

    if "doi" in entry and entry["doi"]:
        citation += f" https://doi.org/{entry['doi']}"

    return citation


def format_mla_citation(entry: dict) -> str:
    """Format citation in MLA style."""
    authors = entry.get("author", "Unknown")
    title = entry.get("title", "").strip("{}")
    year = entry.get("year", "n.d.")

    # Convert "Last, First and Last2, First2" format
    author_parts = authors.split(" and ")
    if len(author_parts) == 1:
        mla_author = authors
    elif len(author_parts) == 2:
        mla_author = f"{author_parts[0]}, and {author_parts[1]}"
    else:
        mla_author = f"{author_parts[0]}, et al."

    citation = f'{mla_author}. "{title}."'

    venue = entry.get("journal") or entry.get("booktitle")
    if venue:
        journal = venue
        citation += f" {journal}"
        if "volume" in entry and entry["volume"]:
            citation += f", vol. {entry['volume']}"
        if "number" in entry and entry["number"]:
            citation += f", no. {entry['number']}"
        if "year" in entry:
            citation += f", {year}"
        if "pages" in entry and entry["pages"]:
            citation += f", pp. {entry['pages']}"
        citation += "."

    return citation


def format_chicago_citation(entry: dict) -> str:
    """Format citation in Chicago style."""
    authors = entry.get("author", "Unknown")
    year = entry.get("year", "n.d.")
    title = entry.get("title", "").strip("{}")

    citation = f'{authors}. "{title}."'

    venue = entry.get("journal") or entry.get("booktitle")
    if venue:
        journal = venue
        citation += f" {journal}"
        if "volume" in entry and entry["volume"]:
            citation += f" {entry['volume']}"
        if "number" in entry and entry["number"]:
            citation += f", no. {entry['number']}"
        if "year" in entry:
            citation += f" ({year})"
        if "pages" in entry and entry["pages"]:
            citation += f": {entry['pages']}"
        citation += "."

    return citation


def format_ieee_citation(entry: dict) -> str:
    """Format citation in IEEE style."""
    authors = entry.get("author", "Unknown")
    author_parts = authors.split(" and ")
    ieee_authors = []

    for author in author_parts[:6]:
        if "," in author:
            last, first = author.split(",", 1)
            first = first.strip()
            if first:
                initials = ". ".join([n[0] for n in first.split()]) + "."
                ieee_authors.append(f"{initials} {last.strip()}")
            else:
                ieee_authors.append(last.strip())

    if len(author_parts) > 6:
        author_str = ", ".join(ieee_authors) + ", et al."
    else:
        author_str = ", ".join(ieee_authors)

    title = entry.get("title", "").strip("{}")
    year = entry.get("year", "n.d.")

    citation = f'{author_str}, "{title},"'

    venue = entry.get("journal") or entry.get("booktitle")
    if venue:
        journal = venue
        citation += f" {journal}"
        if "volume" in entry and entry["volume"]:
            citation += f", vol. {entry['volume']}"
        if "number" in entry and entry["number"]:
            citation += f", no. {entry['number']}"
        if "pages" in entry and entry["pages"]:
            citation += f", pp. {entry['pages']}"
        citation += f", {year}."
    else:
        citation += f" {year}."

    return citation


def format_harvard_citation(entry: dict) -> str:
    """Format citation in Harvard style."""
    authors = entry.get("author", "Unknown")
    year = entry.get("year", "n.d.")
    title = entry.get("title", "").strip("{}")

    author_parts = authors.split(" and ")
    if len(author_parts) > 3:
        first_author = author_parts[0]
        citation = f"{first_author} et al. ({year})"
    else:
        citation = f"{authors} ({year})"

    citation += f" '{title}'"

    venue = entry.get("journal") or entry.get("booktitle")
    if venue:
        journal = venue
        citation += f", {journal}"
        if "volume" in entry and entry["volume"]:
            citation += f", {entry['volume']}"
        if "number" in entry and entry["number"]:
            citation += f"({entry['number']})"
        if "pages" in entry and entry["pages"]:
            citation += f", pp. {entry['pages']}"
        citation += "."

    return citation


def format_vancouver_citation(entry: dict) -> str:
    """Format citation in Vancouver style."""
    authors = entry.get("author", "Unknown")
    author_parts = authors.split(" and ")
    vancouver_authors = []

    for author in author_parts[:6]:
        if "," in author:
            last, first = author.split(",", 1)
            first = first.strip()
            if first:
                initials = "".join([n[0] for n in first.split()])
                vancouver_authors.append(f"{last.strip()} {initials}")
            else:
                vancouver_authors.append(last.strip())

    if len(author_parts) > 6:
        author_str = ", ".join(vancouver_authors) + ", et al."
    else:
        author_str = ", ".join(vancouver_authors)

    title = entry.get("title", "").strip("{}")
    year = entry.get("year", "n.d.")

    citation = f"{author_str}. {title}."

    venue = entry.get("journal") or entry.get("booktitle")
    if venue:
        journal = venue
        citation += f" {journal}."
        if "year" in entry:
            citation += f" {year}"
        if "volume" in entry and entry["volume"]:
            citation += f";{entry['volume']}"
        if "number" in entry and entry["number"]:
            citation += f"({entry['number']})"
        if "pages" in entry and entry["pages"]:
            citation += f":{entry['pages']}"
        citation += "."

    return citation


def format_komorebi_citation(entry: dict) -> str:
    """Format citation in Komorebi style."""
    authors = entry.get("author", "Unknown")
    author_parts = [a.strip() for a in authors.split(" and ")]
    formatted_authors = []

    for author in author_parts[:6]:
        if "," in author:
            last, first = author.split(",", 1)
            first = first.strip()
            if first:
                initials = ". ".join([n[0] for n in first.split()]) + "."
                formatted_authors.append(f"{initials} {last.strip()}")
            else:
                formatted_authors.append(last.strip())
        else:
            formatted_authors.append(author)

    if len(author_parts) > 6:
        author_str = ", ".join(formatted_authors) + " et al."
    elif len(formatted_authors) > 1:
        author_str = ", ".join(formatted_authors[:-1]) + " and " + formatted_authors[-1]
    elif formatted_authors:
        author_str = formatted_authors[0]
    else:
        author_str = authors

    title = entry.get("title", "").strip("{}")
    year = entry.get("year", "n.d.")
    doi = entry.get("doi", "")
    eprint = entry.get("eprint", "")

    citation = f"{author_str}, {title},"

    venue = entry.get("journal") or entry.get("booktitle")
    if venue:
        pages = entry.get("pages", "")

        citation += f" {venue}"
        if entry.get("volume"):
            citation += f" {entry['volume']}"
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

    if doi:
        citation += f"\nhttps://doi.org/{doi}"

    return citation


def format_nature_citation(entry: dict) -> str:
    """Format citation in Nature journal style."""
    authors = entry.get("author", "Unknown")
    author_parts = authors.split(" and ")
    nature_authors = []

    for author in author_parts[:8]:
        if "," in author:
            last, first = author.split(",", 1)
            first = first.strip()
            if first:
                initials = ". ".join([n[0] for n in first.split()]) + "."
                nature_authors.append(f"{last.strip()}, {initials}")
            else:
                nature_authors.append(last.strip())

    if len(author_parts) > 8:
        author_str = ", ".join(nature_authors) + " et al."
    else:
        if len(nature_authors) > 1:
            author_str = " & ".join(
                [" & ".join(nature_authors[:-1]), nature_authors[-1]]
            )
        else:
            author_str = nature_authors[0]

    title = entry.get("title", "").strip("{}")
    year = entry.get("year", "n.d.")

    citation = f"{author_str} {title}."

    venue = entry.get("journal") or entry.get("booktitle")
    if venue:
        journal = venue
        citation += f" {journal}"
        if "volume" in entry and entry["volume"]:
            citation += f" {entry['volume']}"
        if "pages" in entry and entry["pages"]:
            citation += f", {entry['pages']}"
        citation += f" ({year})."

    return citation
