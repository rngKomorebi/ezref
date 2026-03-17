"""EZRef — Streamlit app for academic citation generation."""

import streamlit as st

from api_clients import (
    get_crossref_by_doi,
    get_from_arxiv,
    search_crossref_by_citation,
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

# Page config
st.set_page_config(page_title="EZRef", page_icon="📖", layout="wide")

# Initialize session state
if "entry_dict" not in st.session_state:
    st.session_state.entry_dict = None
if "search_title" not in st.session_state:
    st.session_state.search_title = None
if "arxiv_entry" not in st.session_state:
    st.session_state.arxiv_entry = None
if "last_searched" not in st.session_state:
    st.session_state.last_searched = None


def process_input(user_input: str) -> tuple:
    """Process user input and fetch paper metadata."""
    entry_dict = None
    arxiv_entry = None
    search_title = None

    # Try arXiv first
    arxiv_id = extract_arxiv_id(user_input)
    if arxiv_id:
        st.info(f"Found arXiv ID: {arxiv_id}")
        arxiv_entry = get_from_arxiv(arxiv_id)
        if arxiv_entry:
            entry_dict = make_bib_entry_from_arxiv(arxiv_entry)
            search_title = arxiv_entry.get("title")
            return entry_dict, arxiv_entry, search_title

    # Try DOI extraction
    doi = extract_doi(user_input)
    optica_info = None

    # If URL, extract metadata
    if user_input.startswith("http"):
        if not doi:
            doi = extract_doi(user_input)

        # Handle PDF files
        is_pdf = user_input.lower().endswith(".pdf")
        is_arxiv_pdf = "arxiv.org" in user_input.lower()

        if is_pdf and not is_arxiv_pdf:
            st.info("PDF link detected. Extracting DOI from PDF...")
            pdf_doi = extract_doi_from_pdf(user_input)
            if pdf_doi:
                doi = pdf_doi
                st.success(f"Found DOI in PDF: {doi}")
            else:
                st.warning(
                    "Could not extract DOI. Try the paper's webpage URL."
                )
        elif not is_pdf:
            # Extract metadata from webpage
            try:
                st.info("Fetching metadata from URL...")
                metadata = extract_metadata_from_url(user_input)

                if metadata.get("optica_info"):
                    optica_info = metadata["optica_info"]
                    st.info(
                        f"Found Optica paper: {optica_info['journal']} "
                        f"Vol. {optica_info['volume']}, "
                        f"Issue {optica_info['issue']}, "
                        f"Page {optica_info['page']}"
                    )
                elif metadata["doi"] and not doi:
                    doi = metadata["doi"]
                    st.info(f"Found DOI: {doi}")

                if metadata["title"]:
                    search_title = metadata["title"]
            except Exception as e:
                if not doi:
                    st.warning(f"Could not fetch metadata: {e}")

        # Process Optica info
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
            st.info(f"Using DOI: {doi}")
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


def display_paper_info(entry_dict: dict, arxiv_entry: dict = None):
    """Display paper metadata."""
    st.subheader("Paper Information")

    # Title
    st.markdown(f"**Title:** {entry_dict.get('title', '').strip('{}')}")

    # Two columns for metadata
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Authors:** {entry_dict.get('author', 'N/A')}")
        st.markdown(f"**Year:** {entry_dict.get('year', 'N/A')}")
        if "publisher" in entry_dict and entry_dict["publisher"]:
            st.markdown(f"**Publisher:** {entry_dict['publisher']}")

    with col2:
        if "journal" in entry_dict and entry_dict["journal"]:
            st.markdown(f"**Journal:** {entry_dict.get('journal', 'N/A')}")
        if "volume" in entry_dict and entry_dict["volume"]:
            st.markdown(f"**Volume:** {entry_dict.get('volume', 'N/A')}")
        if "number" in entry_dict and entry_dict["number"]:
            st.markdown(f"**Issue:** {entry_dict.get('number', 'N/A')}")
        if "pages" in entry_dict and entry_dict["pages"]:
            st.markdown(f"**Pages:** {entry_dict['pages']}")

    # Links section
    st.markdown("#### Links & Access")
    if "doi" in entry_dict and entry_dict["doi"]:
        doi_url = f"https://doi.org/{entry_dict['doi']}"
        st.markdown(f"**DOI:** [{entry_dict['doi']}]({doi_url})")

    if entry_dict.get("pdf_url"):
        st.markdown(f"**PDF:** [Publisher PDF]({entry_dict['pdf_url']})")
    elif arxiv_entry:
        arxiv_id = arxiv_entry.get("id").split("/")[-1]
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
        st.markdown(f"**arXiv:** [{arxiv_id}]({arxiv_url})")


def display_citations(entry_dict: dict):
    """Display citations in multiple formats."""
    st.subheader("Citations")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
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

    with tab1:
        bibtex = bib_entry_dict_to_string(entry_dict)
        st.text_area(
            "BibTeX:",
            bibtex,
            height=200,
            label_visibility="collapsed",
            key="bibtex",
        )
        st.download_button(
            label="Download .bib file",
            data=bibtex,
            file_name=f"{entry_dict['ID']}.bib",
            mime="text/plain",
            key="download_bib",
        )

    with tab2:
        apa = format_apa_citation(entry_dict)
        st.markdown("**APA:**")
        st.text_area(
            "Citation:", apa, height=150, label_visibility="collapsed"
        )

    with tab3:
        mla = format_mla_citation(entry_dict)
        st.markdown("**MLA:**")
        st.text_area(
            "Citation:", mla, height=120, label_visibility="collapsed"
        )

    with tab4:
        chicago = format_chicago_citation(entry_dict)
        st.markdown("**Chicago:**")
        st.text_area(
            "Citation:", chicago, height=120, label_visibility="collapsed"
        )

    with tab5:
        ieee = format_ieee_citation(entry_dict)
        st.markdown("**IEEE:**")
        st.text_area(
            "Citation:", ieee, height=120, label_visibility="collapsed"
        )

    with tab6:
        harvard = format_harvard_citation(entry_dict)
        st.markdown("**Harvard:**")
        st.text_area(
            "Citation:", harvard, height=120, label_visibility="collapsed"
        )

    with tab7:
        vancouver = format_vancouver_citation(entry_dict)
        st.markdown("**Vancouver:**")
        st.text_area(
            "Citation:",
            vancouver,
            height=100,
            label_visibility="collapsed",
            key="vancouver",
        )

    with tab8:
        nature = format_nature_citation(entry_dict)
        st.markdown("**Nature:**")
        st.text_area(
            "Citation:",
            nature,
            height=100,
            label_visibility="collapsed",
            key="nature",
        )


# Sidebar settings (evaluated before main content)
with st.sidebar:
    st.header("Settings")
    compact_mode = st.toggle(
        "Compact mode",
        value=False,
        help="Hide paper details, show citations only",
    )


# Main UI
st.title("EZRef")
st.markdown("Generate citations from any paper URL, DOI, or arXiv ID.")

# Input section
user_input = st.text_input(
    "Enter paper URL, DOI, or arXiv ID:",
    placeholder="e.g., https://journals.aps.org/... or "
    "https://arxiv.org/abs/2301.12345 or 10.1103/PhysRevApplied.20.014060",
    key="url_input",
)

# Auto-search only when input changes (prevents re-fetch on sidebar toggles)
auto_search = bool(user_input) and (
    user_input != st.session_state.last_searched
)

# Trigger search
manual_search = st.button("Generate Citation", type="primary")

if manual_search or auto_search:
    with st.spinner("Searching for paper..."):
        try:
            entry_dict, arxiv_entry, search_title = process_input(user_input)

            if entry_dict:
                # Store in session state
                st.session_state.entry_dict = entry_dict
                st.session_state.search_title = search_title
                st.session_state.arxiv_entry = arxiv_entry
                st.session_state.last_searched = user_input

                st.success("Paper found!")
                if not compact_mode:
                    display_paper_info(entry_dict, arxiv_entry)
                display_citations(entry_dict)
            else:
                st.error(
                    "Could not find paper. Please check the input and try again."
                )

        except Exception as e:
            st.error(f"Error: {str(e)}")

# Display results from session state
elif st.session_state.entry_dict is not None:
    entry_dict = st.session_state.entry_dict
    arxiv_entry = st.session_state.arxiv_entry

    st.success("Paper found!")
    if not compact_mode:
        display_paper_info(entry_dict, arxiv_entry)
    display_citations(entry_dict)


# Sidebar
with st.sidebar:
    dark_mode = st.toggle("Dark Mode", value=True)

    if dark_mode:
        st.markdown(
            """
            <style>
            /* Main app background */
            .stApp {
                background-color: #0E1117 !important;
            }
            
            /* Top bar/header */
            header[data-testid="stHeader"] {
                background-color: #0E1117 !important;
            }
            
            /* Sidebar */
            section[data-testid="stSidebar"] {
                background-color: #262730 !important;
            }
            section[data-testid="stSidebar"] .stMarkdown {
                color: #FAFAFA !important;
            }
            
            /* All text colors */
            .stApp * {
                color: #FAFAFA;
            }
            
            /* Text inputs */
            .stTextInput > div > div > input {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border: 1px solid #4A4A4A !important;
            }
            .stTextInput > div > div > input::placeholder {
                color: #808080 !important;
            }
            .stTextInput label {
                color: #FAFAFA !important;
            }
            
            /* Text areas */
            .stTextArea textarea {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border: 1px solid #4A4A4A !important;
            }
            .stTextArea label {
                color: #FAFAFA !important;
            }
            
            /* Code blocks */
            .stCodeBlock, pre {
                background-color: #1E1E1E !important;
            }
            code {
                color: #D4D4D4 !important;
                background-color: #1E1E1E !important;
                padding: 2px 6px !important;
                border-radius: 3px !important;
            }

            /* Inline code in markdown */
            .stMarkdown code {
                color: #87CEEB !important;
                background-color: #1E1E1E !important;
            }
            /* Code in sidebar */
            section[data-testid="stSidebar"] code {
                color: #87CEEB !important;
                background-color: #1E1E1E !important;
            }
            
            /* Tabs */
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
                background-color: rgba(255, 255, 255, 0.05) !important;
            }
            .stTabs [aria-selected="true"] {
                background-color: transparent !important;
                color: #FF6B6B !important;
                border-bottom: 2px solid #FF6B6B !important;
            }
            
            /* Buttons */
            .stButton > button {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border: 1px solid #4A4A4A !important;
            }
            .stButton > button:hover {
                background-color: #3A3A4A !important;
                border: 1px solid #FF6B6B !important;
            }
            .stButton > button[kind="primary"] {
                background-color: #FF6B6B !important;
                color: #FFFFFF !important;
            }
            
            /* Markdown text */
            .stMarkdown, .stMarkdown p, .stMarkdown li {
                color: #FAFAFA !important;
            }
            
            /* Success/Info/Warning/Error boxes */
            .stSuccess {
                background-color: #1B4332 !important;
                color: #95D5B2 !important;
            }
            .stInfo {
                background-color: #1E3A5F !important;
                color: #90CAF9 !important;
            }
            .stWarning {
                background-color: #5C4A1F !important;
                color: #FFD54F !important;
            }
            .stError {
                background-color: #5C1F1F !important;
                color: #EF5350 !important;
            }
            
            /* Download button */
            .stDownloadButton > button {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border: 1px solid #4A4A4A !important;
            }
            
            /* Headers */
            h1, h2, h3, h4, h5, h6 {
                color: #FAFAFA !important;
            }
            
            /* Links */
            a {
                color: #FF6B6B !important;
            }
            a:hover {
                color: #FF8E8E !important;
            }
            
            /* Spinners */
            .stSpinner > div {
                border-top-color: #FF6B6B !important;
            }
            
            /* Captions */
            .stCaption {
                color: #B0B0B0 !important;
            }
            
            /* Dividers */
            hr {
                border-color: #4A4A4A !important;
            }
            
            /* Toggle switch */
            .stCheckbox label {
                color: #FAFAFA !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("**Powered by:** CrossRef API · arXiv API")
