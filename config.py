"""Configuration and constants for the citation generator."""

# API Configuration
CROSSREF_API_URL = "https://api.crossref.org/works"
ARXIV_API_URL = "http://export.arxiv.org/api/query"

# HTTP Configuration
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Timeout settings (in seconds)
PDF_DOWNLOAD_TIMEOUT = 15
URL_FETCH_TIMEOUT = 8
CROSSREF_TIMEOUT = 10
ARXIV_TIMEOUT = 10

# PDF processing
PDF_DOWNLOAD_SIZE = 200000  # bytes (200KB)

# DOI patterns for extraction
DOI_PATTERNS = [
    r"DOI[:\s]*(?:https?://(?:dx\.)?doi\.org/)?(\d+\.\d+/[A-Za-z0-9\.\-\(\)_/]+)",
    r"doi\.org/(\d+\.\d+/[A-Za-z0-9\.\-\(\)_/]+)",
    r"dx\.doi\.org/(\d+\.\d+/[A-Za-z0-9\.\-\(\)_/]+)",
    r"s\d+\-\d+\-\d+\-\d+",  # Nature short DOI format
    r"(?:^|\s|/)(\d+\.\d{4,9}/[A-Za-z0-9\.\-\(\)_/]+)",
]

# arXiv patterns
ARXIV_PATTERNS = [
    r"arxiv\.org/abs/(\d+\.\d+)",
    r"arxiv\.org/pdf/(\d+\.\d+)",
    r"(\d{4}\.\d{4,5})",  # Direct arXiv ID
]

# Optica journal mapping
OPTICA_JOURNALS = {
    "oe": "Optics Express",
    "ol": "Optics Letters",
    "ao": "Applied Optics",
    "josaa": "JOSA A",
    "josab": "JOSA B",
}

# CrossRef type to BibTeX entry type mapping
CROSSREF_TYPE_MAP = {
    "journal-article": "article",
    "proceedings-article": "inproceedings",
    "book-chapter": "incollection",
    "book": "book",
    "report": "techreport",
    "posted-content": "misc",
    "dataset": "misc",
    "reference-entry": "incollection",
}

# BibTeX field order (for consistent formatting)
BIBTEX_FIELD_ORDER = [
    "author",
    "title",
    "journal",
    "booktitle",
    "volume",
    "number",
    "pages",
    "year",
    "month",
    "publisher",
    "doi",
    "url",
    "pdf_url",
]
