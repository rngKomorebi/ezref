"""EZRef — Citation generator & BibTeX cleaner.

Run with:
    streamlit run ezref.py
"""

import re
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog

    _HAS_TKINTER = True
except Exception:
    _HAS_TKINTER = False

import streamlit as st

from api_clients import (
    get_crossref_by_doi,
    get_from_arxiv,
    search_crossref_by_citation,
)
from bib_fix import REQUEST_DELAY
from bib_fix import extract_arxiv_id as _bib_extract_arxiv_id
from bib_fix import (
    extract_citation_keys,
    extract_title_for_doi,
    fetch_arxiv_publication,
    fetch_bibtex_from_doi,
    fetch_doi,
    fetch_doi_for_arxiv,
    insert_doi,
    normalize_entry,
    parse_bib_file,
)
from bibtex_utils import (
    bib_entry_dict_to_string,
    make_bib_entry_from_arxiv,
    make_bib_entry_from_crossref,
)
from formatters import (
    format_apa_citation,
    format_chicago_citation,
    format_harvard_citation,
    format_ieee_citation,
    format_mla_citation,
    format_nature_citation,
    format_vancouver_citation,
)
from parsers import (
    extract_arxiv_id,
    extract_doi,
    extract_doi_from_pdf,
    extract_metadata_from_url,
)

# ── Page configuration ───────────────────────────────────────────────────────
st.set_page_config(page_title="EZRef", page_icon="📖", layout="wide")

# ── Session state defaults ───────────────────────────────────────────────────
for _k, _v in {
    "ct_entry_dict": None,
    "ct_search_title": None,
    "ct_arxiv_entry": None,
    "ct_last_searched": None,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Always hide the sidebar ─────────────────────────────────────────────────
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    button[data-testid="collapsedControl"] { display: none !important; }
    .block-container { max-width: 860px; padding-top: 2rem; }
    [data-testid="stToggle"] label,
    [data-testid="stToggle"] label p,
    [data-testid="stToggle"] label span {
        white-space: nowrap !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Dark mode toggle (top of page, right-aligned) ────────────────────────────
_dm_col, _toggle_col = st.columns([5, 2])
with _toggle_col:
    dark_mode = st.toggle("Dark mode", value=True, key="dark_mode_toggle")

# ── Theme CSS – always injected so component-tree position never changes ─────
# Keeping the st.markdown call unconditional means st.tabs() is always at
# the same tree index, preventing active-tab resets on toggle.
if dark_mode:
    _theme_css = """
        <style>
        .stApp { background-color: #0E1117 !important; }
        header[data-testid="stHeader"] { background-color: #0E1117 !important; }
        .stApp * { color: #FAFAFA; }
        .stTextInput > div > div > input {
            background-color: #262730 !important;
            color: #FAFAFA !important;
            border: 1px solid #4A4A4A !important;
        }
        .stTextInput > div > div > input::placeholder {
            color: #808080 !important;
        }
        .stTextInput label { color: #FAFAFA !important; }
        .stTextArea textarea {
            background-color: #262730 !important;
            color: #FAFAFA !important;
            border: 1px solid #4A4A4A !important;
        }
        .stTextArea label { color: #FAFAFA !important; }
        .stCodeBlock, pre { background-color: #1E1E1E !important; }
        code {
            color: #D4D4D4 !important;
            background-color: #1E1E1E !important;
            padding: 2px 6px !important;
            border-radius: 3px !important;
        }
        .stMarkdown code {
            color: #87CEEB !important;
            background-color: #1E1E1E !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            background-color: transparent !important;
            border-bottom: 1px solid #4A4A4A !important;
        }
        .stTabs [data-baseweb="tab"] {
            color: #FAFAFA !important;
            background-color: transparent !important;
            border: none !important;
            padding: 8px 16px !important;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: rgba(255,255,255,0.05) !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: transparent !important;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            color: #FC7D49 !important;
            border-bottom: 2px solid #FC7D49 !important;
        }
        /* Make all layout containers transparent so dark app bg shows through */
        [data-testid="stColumn"],
        [data-testid="stHorizontalBlock"],
        [data-testid="stVerticalBlock"],
        .stButton,
        [data-testid="stButton"],
        .stButton > div,
        [data-testid="stButton"] > div,
        [data-testid="baseButton-content"] {
            background: transparent !important;
            background-color: transparent !important;
        }
        /* High-specificity button rules beat Streamlit's emotion-cache classes */
        html body .stApp button,
        html body .stApp .stButton > button,
        html body .stApp button[data-testid="baseButton-secondary"] {
            background: #262730 !important;
            background-color: #262730 !important;
            color: #FAFAFA !important;
            border: 1px solid #4A4A4A !important;
        }
        html body .stApp button > div,
        html body .stApp button > div > span {
            background: transparent !important;
            background-color: transparent !important;
        }
        html body .stApp button:hover,
        html body .stApp .stButton > button:hover,
        html body .stApp button[data-testid="baseButton-secondary"]:hover {
            background: #3A3A4A !important;
            background-color: #3A3A4A !important;
            border: 1px solid #FC7D49 !important;
        }
        /* Primary buttons */
        html body .stApp button[data-testid="baseButton-primary"],
        html body .stApp .stButton > button[data-testid="baseButton-primary"] {
            background: #FC7D49 !important;
            background-color: #FC7D49 !important;
            color: #FFFFFF !important;
            border: none !important;
        }
        html body .stApp button[data-testid="baseButton-primary"]:hover,
        html body .stApp .stButton > button[data-testid="baseButton-primary"]:hover {
            background: #e06535 !important;
            background-color: #e06535 !important;
            border: none !important;
        }
        .stMarkdown, .stMarkdown p, .stMarkdown li {
            color: #FAFAFA !important;
        }
        .stSuccess {
            background-color: #1B4332 !important;
            color: #95D5B2 !important;
        }
        .stWarning {
            background-color: #5C4A1F !important;
            color: #FFD54F !important;
        }
        .stError   {
            background-color: #5C1F1F !important;
            color: #EF5350 !important;
        }
        .stDownloadButton > button {
            background-color: #262730 !important;
            color: #FAFAFA !important;
            border: 1px solid #4A4A4A !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #FAFAFA !important; }
        a { color: #FC7D49 !important; }
        a:hover { color: #FFA07A !important; }
        .stSpinner > div { border-top-color: #FC7D49 !important; }
        .stCaption { color: #B0B0B0 !important; }
        hr { border-color: #4A4A4A !important; }
        .stCheckbox label { color: #FAFAFA !important; }
        /* Expander header and body */
        [data-testid="stExpander"] {
            background-color: #1E1E2E !important;
            border: 1px solid #4A4A4A !important;
        }
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary p,
        [data-testid="stExpander"] summary span,
        [data-testid="stExpander"] summary svg {
            background-color: #1E1E2E !important;
            color: #FAFAFA !important;
        }
        [data-testid="stExpander"] > div,
        [data-testid="stExpander"] > details > div,
        [data-testid="stExpanderDetails"] {
            background-color: #1E1E2E !important;
            color: #FAFAFA !important;
        }
        [data-baseweb="accordion"] {
            background-color: #1E1E2E !important;
        }
        [data-baseweb="accordion"] > div,
        [data-baseweb="accordion"] header,
        [data-baseweb="accordion"] header span {
            background-color: #1E1E2E !important;
            color: #FAFAFA !important;
        }
        /* File uploader – cloud mode */
        [data-testid="stFileUploaderDropzone"] {
            background-color: #262730 !important;
            border: 1px solid #4A4A4A !important;
            border-radius: 6px !important;
        }
        [data-testid="stFileUploaderDropzone"] small {
            color: #808080 !important;
        }
        [data-testid="stFileUploaderDropzone"] button {
            background-color: #1E1E2E !important;
            border: 1px solid #4A4A4A !important;
            color: #FAFAFA !important;
        }
        [data-testid="stFileUploaderDropzone"] button:hover {
            background-color: #3A3A4A !important;
            border: 1px solid #FC7D49 !important;
        }
        [data-testid="stFileUploader"] label {
            color: #FAFAFA !important;
        }
        </style>
        """
else:
    _theme_css = """
        <style>
        .stApp { background-color: #FFFFFF !important; }
        header[data-testid="stHeader"] {
            background-color: #F0F2F6 !important;
        }
        .stApp * { color: #31333F; }
        .stTextInput > div > div > input {
            background-color: #FFFFFF !important;
            color: #31333F !important;
            border: 1px solid #CCC !important;
        }
        .stTextInput > div > div > input::placeholder {
            color: #999 !important;
        }
        .stTextInput label { color: #31333F !important; }
        .stTextArea textarea {
            background-color: #FFFFFF !important;
            color: #31333F !important;
            border: 1px solid #CCC !important;
        }
        .stTextArea label { color: #31333F !important; }
        .stCodeBlock, pre { background-color: #F0F2F6 !important; }
        code {
            color: #1E6BA8 !important;
            background-color: #F0F2F6 !important;
            padding: 2px 6px !important;
            border-radius: 3px !important;
        }
        .stMarkdown code {
            color: #1E6BA8 !important;
            background-color: #F0F2F6 !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            background-color: transparent !important;
            border-bottom: 1px solid #E0E0E0 !important;
        }
        .stTabs [data-baseweb="tab"] {
            color: #31333F !important;
            background-color: transparent !important;
            border: none !important;
            padding: 8px 16px !important;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: rgba(0,0,0,0.04) !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: transparent !important;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            color: #FC7D49 !important;
            border-bottom: 2px solid #FC7D49 !important;
        }
        .stButton > button,
        button[data-testid="baseButton-secondary"] {
            background-color: #FFFFFF !important;
            color: #31333F !important;
            border: 1px solid #CCC !important;
        }
        .stButton > button:hover,
        button[data-testid="baseButton-secondary"]:hover {
            background-color: #F0F2F6 !important;
            border: 1px solid #FC7D49 !important;
        }
        /* Primary buttons */
        .stButton > button[data-testid="baseButton-primary"],
        button[data-testid="baseButton-primary"] {
            background-color: #FC7D49 !important;
            color: #FFFFFF !important;
            border: none !important;
        }
        .stButton > button[data-testid="baseButton-primary"]:hover,
        button[data-testid="baseButton-primary"]:hover {
            background-color: #e06535 !important;
            border: none !important;
        }
        .stMarkdown, .stMarkdown p, .stMarkdown li {
            color: #31333F !important;
        }
        .stDownloadButton > button {
            background-color: #FFFFFF !important;
            color: #31333F !important;
            border: 1px solid #CCC !important;
        }
        h1, h2, h3, h4, h5, h6 { color: #0E1117 !important; }
        a { color: #FC7D49 !important; }
        a:hover { color: #FFA07A !important; }
        .stCheckbox label { color: #31333F !important; }
        /* File uploader – cloud mode */
        [data-testid="stFileUploaderDropzone"] {
            background-color: #F8F9FA !important;
            border: 1px solid #CCC !important;
            border-radius: 6px !important;
        }
        [data-testid="stFileUploaderDropzone"] button {
            background-color: #FFFFFF !important;
            border: 1px solid #CCC !important;
            color: #31333F !important;
        }
        [data-testid="stFileUploaderDropzone"] button:hover {
            background-color: #F0F2F6 !important;
            border: 1px solid #FC7D49 !important;
        }
        [data-testid="stFileUploader"] label {
            color: #31333F !important;
        }
        </style>
        """
st.markdown(_theme_css, unsafe_allow_html=True)

# ── Title + tabs ─────────────────────────────────────────────────────────────
st.title("EZRef")
tab_cite, tab_bib = st.tabs(["Citation Lookup", "BibTeX Cleaner"])


# ════════════════════════════════════════════════════════════════════════════
# Helpers – Citation Lookup
# ════════════════════════════════════════════════════════════════════════════


def _process_input(user_input: str) -> tuple:
    """Fetch paper metadata for a URL, DOI, or arXiv ID."""
    entry_dict = None
    arxiv_entry = None
    search_title = None

    # Try arXiv first
    arxiv_id = extract_arxiv_id(user_input)
    if arxiv_id:
        arxiv_entry = get_from_arxiv(arxiv_id)
        if arxiv_entry:
            entry_dict = make_bib_entry_from_arxiv(arxiv_entry)
            search_title = arxiv_entry.get("title")
            return entry_dict, arxiv_entry, search_title

    doi = extract_doi(user_input)
    optica_info = None

    if user_input.startswith("http"):
        is_pdf = user_input.lower().endswith(".pdf")
        is_arxiv_pdf = "arxiv.org" in user_input.lower()

        if is_pdf and not is_arxiv_pdf:
            pdf_doi = extract_doi_from_pdf(user_input)
            if pdf_doi:
                doi = pdf_doi
            else:
                st.warning(
                    "Could not extract DOI from PDF. Try the paper's webpage URL."
                )
        elif not is_pdf:
            try:
                metadata = extract_metadata_from_url(user_input)
                if metadata.get("optica_info"):
                    optica_info = metadata["optica_info"]
                elif metadata["doi"] and not doi:
                    doi = metadata["doi"]
                if metadata["title"] and not search_title:
                    search_title = metadata["title"]
            except Exception as exc:
                if not doi:
                    st.warning(f"Could not fetch metadata: {exc}")

    if optica_info:
        items = search_crossref_by_citation(
            optica_info["journal"],
            optica_info["volume"],
            optica_info["issue"],
            optica_info["page"],
        )
        if items:
            entry_dict = make_bib_entry_from_crossref(items[0])
            search_title = items[0].get("title", [""])[0]
    elif doi:
        item = get_crossref_by_doi(doi)
        if item:
            entry_dict = make_bib_entry_from_crossref(item)
            search_title = item.get("title", [""])[0]
        else:
            st.error(
                "Paper not found in CrossRef. "
                "It may be too recent or not indexed yet."
            )

    return entry_dict, arxiv_entry, search_title


def _display_paper_info(
    entry_dict: dict, arxiv_entry: dict | None = None
) -> None:
    """Render paper metadata."""
    st.subheader("Paper Information")
    st.markdown(f"**Title:** {entry_dict.get('title', '').strip('{}')}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Authors:** {entry_dict.get('author', 'N/A')}")
        st.markdown(f"**Year:** {entry_dict.get('year', 'N/A')}")
        if entry_dict.get("publisher"):
            st.markdown(f"**Publisher:** {entry_dict['publisher']}")
    with col2:
        if entry_dict.get("journal"):
            st.markdown(f"**Journal:** {entry_dict['journal']}")
        if entry_dict.get("volume"):
            st.markdown(f"**Volume:** {entry_dict['volume']}")
        if entry_dict.get("number"):
            st.markdown(f"**Issue:** {entry_dict['number']}")
        if entry_dict.get("pages"):
            st.markdown(f"**Pages:** {entry_dict['pages']}")

    st.markdown("#### Links")
    if entry_dict.get("doi"):
        doi_url = f"https://doi.org/{entry_dict['doi']}"
        st.markdown(f"**DOI:** [{entry_dict['doi']}]({doi_url})")
    if entry_dict.get("pdf_url"):
        st.markdown(f"**PDF:** [Publisher PDF]({entry_dict['pdf_url']})")
    elif arxiv_entry:
        arxiv_id = arxiv_entry.get("id", "").split("/")[-1]
        st.markdown(
            f"**arXiv:** [{arxiv_id}](https://arxiv.org/abs/{arxiv_id})"
        )


def _display_citations(entry_dict: dict) -> None:
    """Render citations in all supported formats."""
    st.subheader("Citations")
    t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(
        [
            "BibTeX",
            "APA",
            "MLA",
            "Chicago",
            "IEEE",
            "Harvard",
            "Vancouver",
            "Nature",
        ]
    )

    with t1:
        bibtex = bib_entry_dict_to_string(entry_dict)
        st.text_area(
            "BibTeX",
            bibtex,
            height=200,
            label_visibility="collapsed",
            key="ct_bibtex",
        )
        st.download_button(
            "Download .bib file",
            data=bibtex,
            file_name=f"{entry_dict['ID']}.bib",
            mime="text/plain",
            key="ct_download_bib",
        )

    for tab_obj, label, fmt_fn, key, h in [
        (t2, "APA", format_apa_citation, "ct_apa", 150),
        (t3, "MLA", format_mla_citation, "ct_mla", 120),
        (t4, "Chicago", format_chicago_citation, "ct_chicago", 120),
        (t5, "IEEE", format_ieee_citation, "ct_ieee", 120),
        (t6, "Harvard", format_harvard_citation, "ct_harvard", 120),
        (t7, "Vancouver", format_vancouver_citation, "ct_vancouver", 100),
        (t8, "Nature", format_nature_citation, "ct_nature", 100),
    ]:
        with tab_obj:
            st.markdown(f"**{label}:**")
            st.text_area(
                "Citation",
                fmt_fn(entry_dict),
                height=h,
                label_visibility="collapsed",
                key=key,
            )


# ════════════════════════════════════════════════════════════════════════════
# Tab 1 – Citation Lookup
# ════════════════════════════════════════════════════════════════════════════

with tab_cite:
    st.markdown("Generate citations from any paper URL, DOI, or arXiv ID.")

    user_input = st.text_input(
        "Enter paper URL, DOI, or arXiv ID:",
        placeholder=(
            "e.g. https://www.jbc.org/article/S0021-9258(19)52451-6/fulltext"
        ),
        key="ct_url_input",
    )

    auto_search = bool(user_input) and (
        user_input != st.session_state.ct_last_searched
    )
    manual_search = st.button(
        "Generate Citation", type="primary", key="ct_search_btn"
    )

    if manual_search or auto_search:
        with st.spinner("Searching…"):
            try:
                entry_dict, arxiv_entry, search_title = _process_input(
                    user_input
                )
                if entry_dict:
                    st.session_state.ct_entry_dict = entry_dict
                    st.session_state.ct_search_title = search_title
                    st.session_state.ct_arxiv_entry = arxiv_entry
                    st.session_state.ct_last_searched = user_input
                    st.success("Paper found!")
                    _display_paper_info(entry_dict, arxiv_entry)
                    _display_citations(entry_dict)
                else:
                    st.error(
                        "Could not find paper. Check the input and try again."
                    )
            except Exception as exc:
                st.error(f"Error: {exc}")

    elif st.session_state.ct_entry_dict is not None:
        entry_dict = st.session_state.ct_entry_dict
        arxiv_entry = st.session_state.ct_arxiv_entry
        st.success("Paper found!")
        _display_paper_info(entry_dict, arxiv_entry)
        _display_citations(entry_dict)


# ════════════════════════════════════════════════════════════════════════════
# Helpers – BibTeX Cleaner
# ════════════════════════════════════════════════════════════════════════════


def _browse_file(state_key: str, filetypes: list) -> None:
    """Open the native OS file picker; stage result in a pending session key."""
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    chosen = filedialog.askopenfilename(filetypes=filetypes)
    root.destroy()
    if chosen:
        st.session_state[f"_{state_key}_pending"] = str(Path(chosen))


def _render_table(rows: list[dict], dark: bool) -> None:
    """Render a list-of-dicts as a full-width HTML table."""
    if not rows:
        return
    bg = "#262730" if dark else "#FFFFFF"
    hdr_bg = "#1A1A2A" if dark else "#F0F2F6"
    txt = "#FAFAFA" if dark else "#31333F"
    border = "#4A4A5A" if dark else "#DDDDDD"
    cell_style = (
        f"padding:5px 10px;border:1px solid {border};"
        f"color:{txt};word-break:break-word;vertical-align:top"
    )
    cols = list(rows[0].keys())
    header_cells = "".join(
        f'<th style="background:{hdr_bg};{cell_style}'
        f';white-space:nowrap;font-weight:600">{c}</th>'
        for c in cols
    )
    body_rows = []
    for row in rows:
        cells = "".join(
            f'<td style="background:{bg};{cell_style}">'
            f"{('Yes' if row[c] is True else 'No' if row[c] is False else row[c])}"
            f"</td>"
            for c in cols
        )
        body_rows.append(f"<tr>{cells}</tr>")
    html = (
        '<div style="overflow-x:auto;width:100%">'
        '<table style="width:100%;border-collapse:collapse;'
        'font-size:0.84rem;table-layout:fixed">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _run_bib_cleaner(
    tex_content: str,
    bib_content: str,
    bib_name: str,
    no_doi: bool,
    keep_unused: bool,
    check_arxiv: bool,
) -> dict:
    """Execute the full BibTeX cleaning pipeline; return a result dict."""

    used_ordered, used_set = extract_citation_keys(tex_content)
    bib_entries = parse_bib_file(bib_content)

    bib_keys = set(bib_entries)
    unused = sorted(bib_keys - used_set)
    missing = sorted(used_set - bib_keys)

    out_keys = list(used_ordered)
    if keep_unused:
        out_keys += [k for k in unused if k in bib_entries]

    # ── Pass 1: normalise + look up missing DOIs ─────────────────────────────
    if not no_doi:
        needs_doi = [
            k
            for k in out_keys
            if k in bib_entries
            and not re.search(
                r"^\s*doi\s*=",
                "".join(bib_entries[k]),
                re.IGNORECASE | re.MULTILINE,
            )
            and extract_title_for_doi(normalize_entry("".join(bib_entries[k])))
        ]
        total_lookups = len(needs_doi)
        lookups_done = 0
        progress = st.progress(0, text="Looking up DOIs via CrossRef…")
    else:
        total_lookups = 0
        progress = None

    entry_lines: dict[str, list[str]] = {}
    doi_added = 0

    for key in out_keys:
        if key not in bib_entries:
            continue
        entry_text = normalize_entry("".join(bib_entries[key]))
        lines = entry_text.splitlines(keepends=True)

        if not no_doi:
            has_doi = re.search(
                r"^\s*doi\s*=", entry_text, re.IGNORECASE | re.MULTILINE
            )
            if not has_doi:
                title = extract_title_for_doi(entry_text)
                if title:
                    doi_val = fetch_doi(title)
                    time.sleep(REQUEST_DELAY)
                    if doi_val:
                        lines = insert_doi(lines, doi_val)
                        doi_added += 1
                    if total_lookups:
                        lookups_done += 1
                        progress.progress(
                            lookups_done / total_lookups,
                            text=(
                                f"Looking up DOIs via CrossRef… "
                                f"{lookups_done}/{total_lookups}"
                            ),
                        )
        entry_lines[key] = lines

    if progress:
        progress.empty()

    # ── Pass 2: arXiv → published journal version ────────────────────────────
    published_after: dict[str, str] = {}
    arxiv_found: list[dict] = []

    if check_arxiv:
        arxiv_keys = [
            (k, _bib_extract_arxiv_id("".join(entry_lines[k])))
            for k in out_keys
            if k in entry_lines
        ]
        arxiv_keys = [(k, aid) for k, aid in arxiv_keys if aid]

        if arxiv_keys:
            arxiv_prog = st.progress(
                0, text="Checking arXiv papers for published versions…"
            )
            for idx, (key, arxiv_id) in enumerate(arxiv_keys, 1):
                source_text = "".join(entry_lines[key])
                pub_key = f"{key}_pub"
                bibtex_added = False
                pub_doi = None
                bibtex = None

                bib_doi_m = re.search(
                    r"^\s*doi\s*=\s*[{\"']\s*([^}\"']+?)\s*[}\"']",
                    source_text,
                    re.IGNORECASE | re.MULTILINE,
                )
                bib_entry_doi = (
                    bib_doi_m.group(1).strip() if bib_doi_m else None
                )

                # Stage 1: arXiv API
                pub = fetch_arxiv_publication(arxiv_id)
                time.sleep(REQUEST_DELAY)
                if pub:
                    if pub.get("doi"):
                        bibtex = fetch_bibtex_from_doi(
                            pub["doi"], pub_key, source_entry=source_text
                        )
                        time.sleep(REQUEST_DELAY)
                        if bibtex:
                            pub_doi = pub["doi"]

                # Stage 2: DOI from the bib entry
                if not bibtex and bib_entry_doi:
                    bibtex = fetch_bibtex_from_doi(
                        bib_entry_doi, pub_key, source_entry=source_text
                    )
                    time.sleep(REQUEST_DELAY)
                    if bibtex:
                        pub_doi = bib_entry_doi
                    else:
                        # Stale/wrong DOI – strip it from the output
                        entry_lines[key] = [
                            ln
                            for ln in entry_lines[key]
                            if not re.match(r"^\s*doi\s*=", ln, re.IGNORECASE)
                        ]

                # Stage 3: CrossRef title + author search
                if not bibtex:
                    cr_doi = fetch_doi_for_arxiv(source_text)
                    time.sleep(REQUEST_DELAY)
                    if cr_doi:
                        bibtex = fetch_bibtex_from_doi(
                            cr_doi, pub_key, source_entry=source_text
                        )
                        time.sleep(REQUEST_DELAY)
                        if bibtex:
                            pub_doi = cr_doi

                if bibtex:
                    published_after[key] = bibtex
                    bibtex_added = True

                arxiv_found.append(
                    {
                        "arXiv key": key,
                        "arXiv ID": arxiv_id,
                        "Published key": pub_key if bibtex_added else "—",
                        "DOI": pub_doi or "—",
                        "BibTeX added": bibtex_added,
                    }
                )
                arxiv_prog.progress(
                    idx / len(arxiv_keys),
                    text=f"Checking arXiv papers… {idx}/{len(arxiv_keys)}",
                )
            arxiv_prog.empty()

    # ── Assemble output ───────────────────────────────────────────────────────
    output_parts: list[str] = []
    written = 0

    for key in out_keys:
        if key not in entry_lines:
            continue
        output_parts.extend(entry_lines[key])
        output_parts.append("\n")
        written += 1
        if key in published_after:
            pub_text = published_after[key].rstrip() + "\n"
            output_parts.extend(pub_text.splitlines(keepends=True))
            output_parts.append("\n")

    return {
        "cleaned_bib": "".join(output_parts),
        "written": written,
        "doi_added": doi_added,
        "no_doi": no_doi,
        "check_arxiv": check_arxiv,
        "arxiv_found": arxiv_found,
        "missing": missing,
        "unused": unused,
        "n_used": len(used_ordered),
        "n_bib": len(bib_entries),
        "out_name": Path(bib_name).stem + "_clean.bib",
    }


# ════════════════════════════════════════════════════════════════════════════
# Tab 2 – BibTeX Cleaner
# ════════════════════════════════════════════════════════════════════════════

with tab_bib:
    st.markdown(
        "Sort, clean, and enrich a `.bib` file based on citation order "
        "in your `.tex` file."
    )

    # Apply any pending browse results BEFORE widgets are instantiated.
    for _wkey in ("bc_tex_path", "bc_bib_path"):
        _pkey = f"_{_wkey}_pending"
        if _pkey in st.session_state:
            st.session_state[_wkey] = st.session_state.pop(_pkey)

    col_tex, col_bib_col = st.columns(2)

    if _HAS_TKINTER:
        # ── Local: path text inputs + native 📂 browse buttons ──────────────
        with col_tex:
            t_inp, t_btn = st.columns([6, 1], vertical_alignment="bottom")
            with t_inp:
                tex_str = st.text_input(
                    "Path to **.tex** file",
                    key="bc_tex_path",
                    placeholder=r"C:\path\to\paper.tex",
                )
            with t_btn:
                if st.button(
                    "📂",
                    key="bc_tex_browse",
                    help="Browse for .tex file",
                    use_container_width=True,
                ):
                    _browse_file(
                        "bc_tex_path",
                        [("TeX files", "*.tex"), ("All files", "*.*")],
                    )
                    st.rerun()
        with col_bib_col:
            b_inp, b_btn = st.columns([6, 1], vertical_alignment="bottom")
            with b_inp:
                bib_str = st.text_input(
                    "Path to **.bib** file",
                    key="bc_bib_path",
                    placeholder=r"C:\path\to\refs.bib",
                )
            with b_btn:
                if st.button(
                    "📂",
                    key="bc_bib_browse",
                    help="Browse for .bib file",
                    use_container_width=True,
                ):
                    _browse_file(
                        "bc_bib_path",
                        [("BibTeX files", "*.bib"), ("All files", "*.*")],
                    )
                    st.rerun()
        tex_file = None
        bib_file = None
    else:
        # ── Cloud: file uploaders ───────────────────────────────────────────
        tex_str = None
        bib_str = None
        with col_tex:
            tex_file = st.file_uploader(
                "Upload **.tex** file",
                type=["tex"],
                key="bc_tex_upload",
            )
        with col_bib_col:
            bib_file = st.file_uploader(
                "Upload **.bib** file",
                type=["bib"],
                key="bc_bib_upload",
            )

    col_opt1, col_opt2, col_opt3 = st.columns(3)
    with col_opt1:
        no_doi = st.checkbox(
            "Skip DOI lookup *(faster / offline)*",
            value=False,
        )
    with col_opt2:
        keep_unused = st.checkbox(
            "Keep unused entries at end of output",
            value=False,
        )
    with col_opt3:
        check_arxiv = st.checkbox(
            "Check arXiv → published",
            value=True,
        )

    run_clean = st.button(
        "Clean BibTeX",
        type="primary",
        use_container_width=True,
        key="bc_run",
    )

    if run_clean:
        errors = []
        if _HAS_TKINTER:
            tex_path = (
                Path(tex_str.strip()) if tex_str and tex_str.strip() else None
            )
            bib_path_val = (
                Path(bib_str.strip()) if bib_str and bib_str.strip() else None
            )
            if not tex_path:
                errors.append("Please provide a path to the `.tex` file.")
            elif not tex_path.exists():
                errors.append(f"`.tex` file not found: `{tex_path}`")
            if not bib_path_val:
                errors.append("Please provide a path to the `.bib` file.")
            elif not bib_path_val.exists():
                errors.append(f"`.bib` file not found: `{bib_path_val}`")
        else:
            tex_path = None
            bib_path_val = None
            if not tex_file:
                errors.append("Please upload a `.tex` file.")
            if not bib_file:
                errors.append("Please upload a `.bib` file.")

        if errors:
            for msg in errors:
                st.error(msg)
            st.stop()

        if _HAS_TKINTER:
            tex_content = tex_path.read_text(encoding="utf-8")
            bib_content = bib_path_val.read_text(encoding="utf-8")
            bib_name = bib_path_val.name
        else:
            tex_content = tex_file.read().decode("utf-8")
            bib_content = bib_file.read().decode("utf-8")
            bib_name = bib_file.name

        with st.spinner("Processing…"):
            st.session_state["bc_result"] = _run_bib_cleaner(
                tex_content,
                bib_content,
                bib_name,
                no_doi,
                keep_unused,
                check_arxiv,
            )

    if "bc_result" in st.session_state:
        r = st.session_state["bc_result"]
        arxiv_found = r.get("arxiv_found", [])

        if r["missing"]:
            with st.expander(
                f"{len(r['missing'])} cited key(s) not found in the .bib",
                expanded=True,
            ):
                st.code(
                    "\n".join(f"- {k}" for k in r["missing"]), language=None
                )

        if r["unused"]:
            n = len(r["unused"])
            with st.expander(
                f"{n} .bib entr{'y' if n == 1 else 'ies'} never cited in the .tex"
            ):
                st.code(
                    "\n".join(f"- {k}" for k in r["unused"]), language=None
                )

        if r.get("check_arxiv"):
            if arxiv_found:
                n_bib = sum(1 for x in arxiv_found if x["BibTeX added"])
                with st.expander(
                    f"{len(arxiv_found)} arXiv paper(s) found – "
                    f"{n_bib} published entr{'y' if n_bib == 1 else 'ies'} added",
                    expanded=True,
                ):
                    _render_table(arxiv_found, dark_mode)

        doi_msg = (
            f" · {r['doi_added']} DOI(s) added" if not r["no_doi"] else ""
        )
        pub_count = sum(1 for x in arxiv_found if x["BibTeX added"])
        pub_msg = (
            f" · {pub_count} published version(s) inserted"
            if pub_count
            else ""
        )
        st.success(f"{r['written']} entries written{doi_msg}{pub_msg}")

        st.subheader("Cleaned .bib")
        st.text_area(
            "cleaned_bib",
            r["cleaned_bib"],
            height=420,
            label_visibility="collapsed",
            key="bc_output_area",
        )
        st.download_button(
            f"Download  {r['out_name']}",
            data=r["cleaned_bib"].encode("utf-8"),
            file_name=r["out_name"],
            mime="text/plain",
            use_container_width=True,
            key="bc_download",
        )
