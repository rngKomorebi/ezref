# EZRef

A Streamlit web app for generating academic citations from paper URLs, DOIs, or arXiv IDs.

## Features

- **Multiple Input Methods**: URL, DOI, or arXiv ID
- **8 Citation Formats**: BibTeX, APA, MLA, Chicago, IEEE, Harvard, Vancouver, Nature
- **Smart Metadata Extraction**: Automatically extracts metadata from publisher webpages
- **PDF DOI Extraction**: Can extract DOIs directly from PDF files
- **arXiv Integration**: Automatically finds and links to arXiv versions
- **Export BibTeX**: Download citations as .bib files

## Quick Start - local deployment

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the app:
```bash
streamlit run ezref.py
```

## Project Structure

```
ezref/
├── ezref.py               # Main Streamlit app
├── config.py              # Configuration and constants
├── api_clients.py         # CrossRef and arXiv API clients
├── parsers.py             # DOI/arXiv/URL extraction
├── formatters.py          # Citation format functions
├── bibtex_utils.py        # BibTeX utilities
├── requirements.txt       # Dependencies
├── .streamlit/
│   └── config.toml        # Streamlit theme and server config
└── README.md              # This file
```

## Supported Publishers

- **arXiv**: Direct integration with arXiv API
- **CrossRef Members**: Nature, Science, IEEE, APS, Springer, Elsevier, etc.
- **PDF Files**: Can extract DOIs from PDF content

## Example Inputs

### arXiv
- `https://arxiv.org/abs/2301.12345`
- `2301.12345`

### DOI
- `https://doi.org/10.1038/nature12345`
- `10.1038/nature12345`

### Publisher URLs
- `https://opg.optica.org/oe/fulltext.cfm?uri=oe-29-18-28217`
- `https://journals.aps.org/prapplied/abstract/10.1103/PhysRevApplied.20.014060`
- `https://www.nature.com/articles/s41467-025-63830-3`

## API Usage

The app uses:
- **CrossRef API**: For published paper metadata
- **arXiv API**: For preprint metadata

No API keys required!

## License

[MIT License](LICENSE) - feel free to use and modify!

## Credits

Powered by:
- [CrossRef API](https://www.crossref.org/services/metadata-delivery/)
- [arXiv API](https://arxiv.org/help/api/)
- [Streamlit](https://streamlit.io/)
