# EZRef

A Streamlit web app with two tools for academic writing:

- **Citation Lookup** — generate formatted citations from any paper URL, DOI, or arXiv ID
- **BibTeX Cleaner** — sort, deduplicate, and enrich a `.bib` file based on citation order in your `.tex` file

## Quick Start

```bash
pip install -r requirements.txt
streamlit run ezref.py
```

The app opens automatically in your browser (dark mode on by default).

---

## Tab 1 — Citation Lookup

Paste a paper URL, DOI, or arXiv ID and get:

- Paper metadata (title, authors, journal, year, DOI)
- Citations in **8 formats**: BibTeX, APA, MLA, Chicago, IEEE, Harvard, Vancouver, Nature
- One-click `.bib` file download

### Supported inputs

| Type | Example |
|------|---------|
| arXiv URL | `https://arxiv.org/abs/2301.12345` |
| arXiv ID | `2301.12345` |
| DOI URL | `https://doi.org/10.1038/nature12345` |
| DOI | `10.1038/nature12345` |
| Nature | `https://www.nature.com/articles/s41467-025-63830-3` |
| APS | `https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.130.093001` |
| Optica | `https://opg.optica.org/oe/fulltext.cfm?uri=oe-29-18-28217` |
| Elsevier / JBC | `https://www.jbc.org/article/S0021-9258(19)52451-6/fulltext` |
| PDF URL | `https://example.com/paper.pdf` |

---

## Tab 2 — BibTeX Cleaner

Point the app at your `.tex` and `.bib` files. It will:

1. Extract all citation keys from the `.tex` in first-appearance order
2. Report keys **cited but missing** from the `.bib`
3. Report `.bib` entries **never cited** in the `.tex`
4. Normalize entries: double-brace titles, fix page dashes (`1-10` → `1--10`)
5. Look up and insert **missing DOIs** via the CrossRef API *(optional)*
6. Check each arXiv entry for a **published journal version** and insert a second BibTeX entry when found *(optional)*
7. Write a clean output `.bib` in citation order

### Options

| Option | Default | Description |
|--------|---------|-------------|
| Skip DOI lookup | Off | Faster / works offline |
| Keep unused entries | Off | Appends uncited entries at the end |
| Check arXiv → published | On | Finds published versions of arXiv preprints via CrossRef |

---

## Project Structure

```
ezref/
├── ezref.py               # Main Streamlit app (two tabs)
├── bib_fix.py             # BibTeX cleaning library (also CLI-runnable)
├── config.py              # API URLs, timeouts, regex patterns
├── api_clients.py         # CrossRef and arXiv API clients
├── parsers.py             # DOI / arXiv / URL / PDF metadata extraction
├── formatters.py          # Citation formatters (APA, MLA, Chicago, …)
├── bibtex_utils.py        # BibTeX entry building and serialisation
├── test_ezref.py          # pytest suite (100 tests)
├── requirements.txt       # Python dependencies
├── .streamlit/
│   └── config.toml        # Theme and server settings
└── README.md              # This file
```

---

## Dependencies

No API keys required.

```
streamlit>=1.30.0
requests>=2.31.0
beautifulsoup4>=4.12.0
feedparser>=6.0.10
pytest>=7.0
```

---

## License

[MIT License](LICENSE)
