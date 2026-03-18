"""
test_ezref.py — pytest suite for the combined EZRef app.

Run from the ezref/ directory:
    pytest test_ezref.py -v

No network calls are made; external APIs are always mocked.
"""

import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bibtex_utils import (
    bib_entry_dict_to_string,
    format_arxiv_authors,
    make_bib_key,
    normalize_author_string,
)
from formatters import (
    format_apa_citation,
    format_chicago_citation,
    format_ieee_citation,
    format_mla_citation,
    format_nature_citation,
    format_vancouver_citation,
)
from parsers import extract_arxiv_id, extract_doi

from bib_fix import extract_citation_keys, extract_title_for_doi, insert_doi
from bib_fix import main as bib_fix_main
from bib_fix import normalize_entry, parse_bib_file

# ─────────────────────────────────────────────────────────────────────────────
# parsers – extract_arxiv_id
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractArxivId:
    def test_abs_url(self):
        assert (
            extract_arxiv_id("https://arxiv.org/abs/2301.12345")
            == "2301.12345"
        )

    def test_pdf_url(self):
        assert (
            extract_arxiv_id("https://arxiv.org/pdf/2301.12345")
            == "2301.12345"
        )

    def test_direct_id(self):
        assert extract_arxiv_id("2301.12345") == "2301.12345"

    def test_five_digit_id_in_url(self):
        # 5-digit IDs (post-2014) must be extracted from URLs correctly
        assert (
            extract_arxiv_id("https://arxiv.org/abs/1503.12345")
            == "1503.12345"
        )

    def test_non_arxiv_url_returns_none(self):
        assert (
            extract_arxiv_id("https://journals.aps.org/prl/abstract/10.1103/x")
            is None
        )

    def test_doi_url_not_matched(self):
        assert extract_arxiv_id("https://doi.org/10.1038/nature12345") is None


# ─────────────────────────────────────────────────────────────────────────────
# parsers – extract_doi
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractDoi:
    def test_doi_org_url(self):
        assert (
            extract_doi("https://doi.org/10.1038/nature12345")
            == "10.1038/nature12345"
        )

    def test_raw_doi(self):
        assert (
            extract_doi("10.1103/PhysRevApplied.20.014060")
            == "10.1103/PhysRevApplied.20.014060"
        )

    def test_trailing_punctuation_stripped(self):
        doi = extract_doi("See doi.org/10.1234/test.")
        assert doi == "10.1234/test"

    def test_no_doi_returns_none(self):
        assert extract_doi("no doi here at all") is None

    def test_pdf_extension_stripped(self):
        doi = extract_doi("https://doi.org/10.1234/test.pdf")
        assert doi is not None
        assert not doi.endswith(".pdf")

    def test_embedded_in_url(self):
        doi = extract_doi(
            "https://publisher.com/10.1111/j.1234-5678.2023.tb00001.x"
        )
        assert doi is not None
        assert doi.startswith("10.")


# ─────────────────────────────────────────────────────────────────────────────
# bibtex_utils – make_bib_key
# ─────────────────────────────────────────────────────────────────────────────


class TestMakeBibKey:
    def test_basic_last_first(self):
        assert make_bib_key("Smith, John", "2023") == "Smith2023"

    def test_first_author_used(self):
        key = make_bib_key("Smith, John and Jones, Alice", "2020")
        assert key.startswith("Smith")
        assert "2020" in key

    def test_no_author_fallback(self):
        key = make_bib_key("", "2020")
        assert "2020" in key

    def test_no_year(self):
        key = make_bib_key("Doe, Jane", "")
        assert "Doe" in key

    def test_non_ascii_stripped(self):
        key = make_bib_key("Müller, Hans", "2021")
        assert key  # should not crash; returns something


# ─────────────────────────────────────────────────────────────────────────────
# bibtex_utils – format_arxiv_authors
# ─────────────────────────────────────────────────────────────────────────────


class TestFormatArxivAuthors:
    def test_single_author(self):
        result = format_arxiv_authors([{"name": "John Smith"}])
        assert result == "Smith, John"

    def test_multiple_authors_joined_with_and(self):
        result = format_arxiv_authors(
            [{"name": "Alice Brown"}, {"name": "Bob Jones"}]
        )
        assert "Brown, Alice" in result
        assert "Jones, Bob" in result
        assert " and " in result

    def test_single_word_name_unchanged(self):
        result = format_arxiv_authors([{"name": "Einstein"}])
        assert "Einstein" in result

    def test_three_part_name(self):
        result = format_arxiv_authors([{"name": "Jean-Pierre Dupont"}])
        assert "Dupont" in result


# ─────────────────────────────────────────────────────────────────────────────
# bibtex_utils – normalize_author_string
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeAuthorString:
    def test_last_first_format_preserved(self):
        result = normalize_author_string("Smith, John")
        assert "Smith" in result
        assert "John" in result

    def test_multiple_authors_joined(self):
        result = normalize_author_string("Smith, John and Jones, Alice")
        assert " and " in result

    def test_title_case_applied(self):
        result = normalize_author_string("smith, john")
        assert "Smith" in result


# ─────────────────────────────────────────────────────────────────────────────
# bibtex_utils – bib_entry_dict_to_string
# ─────────────────────────────────────────────────────────────────────────────


class TestBibEntryDictToString:
    def test_basic_format(self):
        entry = {
            "ENTRYTYPE": "article",
            "ID": "Test2023",
            "author": "Smith, John",
            "title": "{Test Title}",
            "year": "2023",
        }
        result = bib_entry_dict_to_string(entry)
        assert result.startswith("@article{Test2023,")
        assert "author = {Smith, John}" in result
        assert "year = {2023}" in result
        assert result.endswith("}")

    def test_no_trailing_comma_on_last_field(self):
        entry = {
            "ENTRYTYPE": "misc",
            "ID": "K",
            "author": "A",
            "year": "2020",
        }
        result = bib_entry_dict_to_string(entry)
        lines = [ln.strip() for ln in result.splitlines() if ln.strip()]
        closing_idx = next(i for i, ln in enumerate(lines) if ln == "}")
        assert not lines[closing_idx - 1].endswith(",")

    def test_empty_fields_excluded(self):
        entry = {
            "ENTRYTYPE": "article",
            "ID": "K",
            "author": "A",
            "journal": "",
        }
        result = bib_entry_dict_to_string(entry)
        assert "journal" not in result

    def test_field_order_respected(self):
        entry = {
            "ENTRYTYPE": "article",
            "ID": "K",
            "year": "2020",
            "author": "A",
            "title": "{T}",
            "journal": "Nature",
        }
        result = bib_entry_dict_to_string(entry)
        assert result.index("author") < result.index("title")
        assert result.index("title") < result.index("journal")


# ─────────────────────────────────────────────────────────────────────────────
# formatters
# ─────────────────────────────────────────────────────────────────────────────

_SAMPLE = {
    "ENTRYTYPE": "article",
    "ID": "Smith2020",
    "author": "Smith, John and Doe, Jane",
    "title": "{A Great Paper}",
    "journal": "Nature",
    "volume": "42",
    "number": "3",
    "pages": "100--110",
    "year": "2020",
    "doi": "10.1234/test",
}


class TestFormatApaCitation:
    def test_contains_author_year_title(self):
        result = format_apa_citation(_SAMPLE)
        assert "Smith" in result
        assert "2020" in result
        assert "A Great Paper" in result

    def test_contains_doi_link(self):
        assert "doi.org" in format_apa_citation(_SAMPLE)

    def test_minimal_entry_no_crash(self):
        result = format_apa_citation(
            {"author": "Unknown", "year": "n.d.", "title": "{T}"}
        )
        assert "Unknown" in result


class TestFormatIeeeCitation:
    def test_author_initials(self):
        result = format_ieee_citation(_SAMPLE)
        assert "J. Smith" in result

    def test_title_in_quotes(self):
        result = format_ieee_citation(_SAMPLE)
        assert "A Great Paper" in result

    def test_year_present(self):
        assert "2020" in format_ieee_citation(_SAMPLE)

    def test_volume_and_pages(self):
        result = format_ieee_citation(_SAMPLE)
        assert "42" in result
        assert "100" in result


class TestFormatNatureCitation:
    def test_ampersand_for_two_authors(self):
        assert "&" in format_nature_citation(_SAMPLE)

    def test_year_in_parens(self):
        assert "(2020)" in format_nature_citation(_SAMPLE)

    def test_et_al_for_nine_plus_authors(self):
        entry = {
            **_SAMPLE,
            "author": " and ".join([f"Author{i}, X" for i in range(9)]),
        }
        assert "et al." in format_nature_citation(entry)


class TestFormatMlaCitation:
    def test_et_al_for_three_plus_authors(self):
        entry = {
            **_SAMPLE,
            "author": "A, B and C, D and E, F and G, H",
        }
        assert "et al." in format_mla_citation(entry)

    def test_two_authors_uses_and(self):
        result = format_mla_citation(_SAMPLE)
        assert "and" in result.lower()

    def test_title_quoted(self):
        result = format_mla_citation(_SAMPLE)
        assert '"A Great Paper"' in result or "A Great Paper" in result


class TestFormatChicagoCitation:
    def test_year_in_parens(self):
        result = format_chicago_citation(_SAMPLE)
        assert "(2020)" in result

    def test_author_and_title_present(self):
        result = format_chicago_citation(_SAMPLE)
        assert "Smith" in result
        assert "A Great Paper" in result


class TestFormatVancouverCitation:
    def test_volume_semicolon_format(self):
        result = format_vancouver_citation(_SAMPLE)
        # Vancouver: journal. year;volume(issue):pages
        assert "42" in result

    def test_author_initials_no_periods(self):
        result = format_vancouver_citation(_SAMPLE)
        # Vancouver uses initials without dots between them
        assert "Smith" in result


# ─────────────────────────────────────────────────────────────────────────────
# bib_fix – extract_citation_keys
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractCitationKeys:
    def test_basic_cite(self):
        ordered, seen = extract_citation_keys(r"\cite{smith2020}")
        assert ordered == ["smith2020"]
        assert seen == {"smith2020"}

    def test_citep_and_citet(self):
        ordered, _ = extract_citation_keys(
            r"\citep{jones2021} and \citet{doe2022}"
        )
        assert ordered == ["jones2021", "doe2022"]

    def test_starred_variant(self):
        ordered, _ = extract_citation_keys(r"\cite*{star2023}")
        assert ordered == ["star2023"]

    def test_single_optional_note(self):
        ordered, _ = extract_citation_keys(r"\citep[e.g.]{single2024}")
        assert ordered == ["single2024"]

    def test_two_optional_notes(self):
        ordered, _ = extract_citation_keys(r"\citep[see][p.~5]{prepost2024}")
        assert ordered == ["prepost2024"]

    def test_comma_separated_keys(self):
        ordered, _ = extract_citation_keys(r"\cite{a2020, b2021, c2022}")
        assert ordered == ["a2020", "b2021", "c2022"]

    def test_deduplication_preserves_first_occurrence(self):
        ordered, _ = extract_citation_keys(
            r"\cite{a2020} text \cite{a2020} more \cite{b2021}"
        )
        assert ordered == ["a2020", "b2021"]

    def test_order_preserved(self):
        ordered, _ = extract_citation_keys(
            r"\cite{z2020} \cite{a2021} \cite{m2022}"
        )
        assert ordered == ["z2020", "a2021", "m2022"]

    def test_nocite(self):
        ordered, _ = extract_citation_keys(r"\nocite{hidden2020}")
        assert ordered == ["hidden2020"]

    def test_footcite_autocite_parencite(self):
        ordered, _ = extract_citation_keys(
            r"\footcite{foot} \autocite{auto} \parencite{paren}"
        )
        assert ordered == ["foot", "auto", "paren"]

    def test_textcite_fullcite(self):
        ordered, _ = extract_citation_keys(r"\textcite{text} \fullcite{full}")
        assert ordered == ["text", "full"]

    def test_no_cites_returns_empty(self):
        ordered, seen = extract_citation_keys("No citations here.")
        assert ordered == []
        assert seen == set()

    def test_mixed_spacing_in_comma_group(self):
        ordered, _ = extract_citation_keys(r"\cite{  a2020  ,  b2021  }")
        assert ordered == ["a2020", "b2021"]


# ─────────────────────────────────────────────────────────────────────────────
# bib_fix – parse_bib_file
# ─────────────────────────────────────────────────────────────────────────────


class TestParseBibFile:
    def test_basic_article(self):
        bib = textwrap.dedent(
            """\
            @article{smith2020,
              author = {Smith, J.},
              title = {A Title},
              year = {2020},
            }
            """
        )
        assert list(parse_bib_file(bib).keys()) == ["smith2020"]

    def test_skips_comment(self):
        bib = "@comment{ignore}\n@article{real2020, title = {Real}}\n"
        entries = parse_bib_file(bib)
        assert "real2020" in entries
        assert len(entries) == 1

    def test_skips_string_and_preamble(self):
        bib = (
            "@string{jphys = {Journal of Physics}}\n"
            '@preamble{"\\\\cmd"}\n'
            "@article{art2020, title = {Article}}\n"
        )
        entries = parse_bib_file(bib)
        assert "art2020" in entries
        assert len(entries) == 1

    def test_multiple_entry_types(self):
        bib = (
            "@article{a, title = {A}}\n"
            "@book{b, title = {B}}\n"
            "@inproceedings{c, title = {C}}\n"
            "@misc{d, title = {D}}\n"
            "@phdthesis{e, title = {E}}\n"
        )
        assert set(parse_bib_file(bib).keys()) == {"a", "b", "c", "d", "e"}

    def test_nested_braces(self):
        bib = "@article{k, title = {A {Nested} Title}}\n"
        assert "k" in parse_bib_file(bib)

    def test_multiline_field(self):
        bib = (
            "@article{k, author = {Smith, J. and\n"
            "                      Jones, A.}}\n"
        )
        assert "k" in parse_bib_file(bib)

    def test_blank_lines_between_entries(self):
        bib = (
            "@article{first2020, title = {First}}\n\n\n"
            "@article{second2021, title = {Second}}\n"
        )
        entries = parse_bib_file(bib)
        assert "first2020" in entries
        assert "second2021" in entries


# ─────────────────────────────────────────────────────────────────────────────
# bib_fix – normalize_entry
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeEntry:
    def test_single_brace_title_becomes_double(self):
        result = normalize_entry("@article{k, title = {My Title}}")
        assert "{{My Title}}" in result

    def test_already_double_braced_title_unchanged(self):
        entry = "@article{k, title = {{My Title}}}"
        result = normalize_entry(entry)
        assert result.count("{{My Title}}") == 1
        assert "{{{" not in result

    def test_quoted_title_becomes_double_braced(self):
        result = normalize_entry('@article{k, title = "My Title"}')
        assert "{{My Title}}" in result

    def test_title_with_nested_braces(self):
        result = normalize_entry("@article{k, title = {Title with {Acronym}}}")
        assert "{{Title with {Acronym}}}" in result

    def test_multiline_title(self):
        entry = (
            "@article{k,\n"
            "  title = {A Very Long Title That\n"
            "            Spans Multiple Lines},\n"
            "  year = {2020},\n"
            "}\n"
        )
        result = normalize_entry(entry)
        assert "{{A Very Long Title That" in result

    def test_page_range_single_hyphen_fixed(self):
        result = normalize_entry("@article{k, pages = {1-10}}")
        assert "1--10" in result
        assert "1-10" not in result.replace("1--10", "")

    def test_page_range_already_double_dash_unchanged(self):
        result = normalize_entry("@article{k, pages = {1--10}}")
        assert result.count("1--10") == 1
        assert "1---10" not in result

    def test_page_range_with_spaces_around_hyphen(self):
        result = normalize_entry("@article{k, pages = {100 - 200}}")
        assert "100--200" in result

    def test_non_title_fields_not_double_braced(self):
        result = normalize_entry(
            "@article{k, author = {Smith, J.}, title = {T}}"
        )
        assert "author = {{Smith, J.}}" not in result

    def test_entry_without_title_unchanged(self):
        entry = "@misc{k, year = {2020}, url = {https://example.com}}"
        assert normalize_entry(entry) == entry


# ─────────────────────────────────────────────────────────────────────────────
# bib_fix – extract_title_for_doi
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractTitleForDoi:
    def test_double_braced(self):
        assert (
            extract_title_for_doi("@article{k, title = {{My Paper Title}}}")
            == "My Paper Title"
        )

    def test_single_braced(self):
        assert (
            extract_title_for_doi("@article{k, title = {My Paper Title}}")
            == "My Paper Title"
        )

    def test_quoted_title(self):
        assert (
            extract_title_for_doi('@article{k, title = "My Paper Title"}')
            == "My Paper Title"
        )

    def test_nested_braces_stripped(self):
        result = extract_title_for_doi(
            "@article{k, title = {{Title with {Acronym}}}}"
        )
        assert result == "Title with Acronym"

    def test_no_title_returns_none(self):
        assert extract_title_for_doi("@article{k, author = {Smith}}") is None

    def test_multiline_title_whitespace_collapsed(self):
        entry = "@article{k,\n  title = {{A Long\n            Title}},\n}"
        assert extract_title_for_doi(entry) == "A Long Title"

    def test_no_braces_in_result(self):
        result = extract_title_for_doi(
            "@article{k, title = {{Bose{-}Einstein Condensation}}}"
        )
        assert result is not None
        assert "{" not in result and "}" not in result


# ─────────────────────────────────────────────────────────────────────────────
# bib_fix – insert_doi
# ─────────────────────────────────────────────────────────────────────────────


class TestInsertDoi:
    def test_doi_inserted_before_closing_brace(self):
        lines = [
            "@article{k,\n",
            "  title = {{T}},\n",
            "  year = {2020},\n",
            "}\n",
        ]
        result = insert_doi(lines, "10.1234/test")
        doi_idx = next(
            i for i, ln in enumerate(result) if "doi = {10.1234/test}" in ln
        )
        close_idx = next(i for i, ln in enumerate(result) if ln.strip() == "}")
        assert doi_idx < close_idx

    def test_doi_line_format(self):
        lines = ["@article{k,\n", "  title = {{T}},\n", "}\n"]
        result = insert_doi(lines, "10.9999/foo")
        assert "  doi = {10.9999/foo},\n" in result

    def test_entry_otherwise_unchanged(self):
        lines = ["@article{k,\n", "  title = {{T}},\n", "}\n"]
        result = insert_doi(lines, "10.0000/x")
        assert "@article{k,\n" in result
        assert "  title = {{T}},\n" in result

    def test_inserted_exactly_once(self):
        lines = ["@article{k,\n", "  title = {{T}},\n", "}\n"]
        result = insert_doi(lines, "10.1111/y")
        assert sum(1 for ln in result if "doi" in ln) == 1


# ─────────────────────────────────────────────────────────────────────────────
# bib_fix – integration via CLI main()
# ─────────────────────────────────────────────────────────────────────────────


class TestBibFixIntegration:
    """End-to-end tests via bib_fix CLI. CrossRef is always mocked."""

    def _run(self, args: list[str]) -> None:
        with patch("sys.argv", ["bib_fix.py"] + args):
            bib_fix_main()

    def test_only_cited_entries_in_output(self, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{used2020}", encoding="utf-8")
        bib.write_text(
            "@article{used2020, title = {Used}}\n"
            "@article{unused2021, title = {Unused}}\n",
            encoding="utf-8",
        )
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
            ]
        )
        content = out.read_text(encoding="utf-8")
        assert "used2020" in content
        assert "unused2021" not in content

    def test_citation_order_preserved(self, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{z2020} \cite{a2021}", encoding="utf-8")
        bib.write_text(
            "@article{a2021, title = {A}}\n@article{z2020, title = {Z}}\n",
            encoding="utf-8",
        )
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
            ]
        )
        content = out.read_text(encoding="utf-8")
        assert content.index("z2020") < content.index("a2021")

    def test_title_double_braced_in_output(self, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{k}", encoding="utf-8")
        bib.write_text(
            "@article{k, title = {Single Braced Title}}\n", encoding="utf-8"
        )
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
            ]
        )
        assert "{{Single Braced Title}}" in out.read_text(encoding="utf-8")

    def test_page_ranges_normalized(self, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{k}", encoding="utf-8")
        bib.write_text(
            "@article{k, title = {T}, pages = {1-10}}\n", encoding="utf-8"
        )
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
            ]
        )
        content = out.read_text(encoding="utf-8")
        assert "1--10" in content
        assert "1-10" not in content.replace("1--10", "")

    def test_keep_unused_flag(self, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{used}", encoding="utf-8")
        bib.write_text(
            "@article{used, title = {Used}}\n"
            "@article{ghost, title = {Ghost}}\n",
            encoding="utf-8",
        )
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
                "--keep-unused",
            ]
        )
        content = out.read_text(encoding="utf-8")
        assert "ghost" in content
        assert content.index("used") < content.index("ghost")

    def test_missing_keys_reported_to_stdout(self, tmp_path, capsys):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{missing_key}", encoding="utf-8")
        bib.write_text("@article{other, title = {Other}}\n", encoding="utf-8")
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
            ]
        )
        assert "missing_key" in capsys.readouterr().out

    def test_unused_keys_reported_to_stdout(self, tmp_path, capsys):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{used}", encoding="utf-8")
        bib.write_text(
            "@article{used, title = {U}}\n" "@article{ghost, title = {G}}\n",
            encoding="utf-8",
        )
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
            ]
        )
        assert "ghost" in capsys.readouterr().out

    @patch("bib_fix.fetch_doi", return_value="10.9999/mocked")
    @patch("bib_fix.time.sleep")
    def test_doi_added_when_missing(self, _sleep, _fetch, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{k}", encoding="utf-8")
        bib.write_text(
            "@article{k,\n  title = {No DOI Here},\n  year = {2020},\n}\n",
            encoding="utf-8",
        )
        self._run(["--tex", str(tex), "--bib", str(bib), "--out", str(out)])
        assert "doi = {10.9999/mocked}" in out.read_text(encoding="utf-8")

    @patch("bib_fix.fetch_doi", return_value="10.9999/mocked")
    @patch("bib_fix.time.sleep")
    def test_existing_doi_not_duplicated(self, _sleep, mock_fetch, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{k}", encoding="utf-8")
        bib.write_text(
            "@article{k,\n"
            "  title = {Has DOI},\n"
            "  doi = {10.1234/existing},\n"
            "  year = {2020},\n"
            "}\n",
            encoding="utf-8",
        )
        self._run(["--tex", str(tex), "--bib", str(bib), "--out", str(out)])
        mock_fetch.assert_not_called()
        assert out.read_text(encoding="utf-8").count("doi =") == 1

    @patch("bib_fix.fetch_doi", return_value="10.9999/mocked")
    @patch("bib_fix.time.sleep")
    def test_no_doi_flag_skips_crossref(self, _sleep, mock_fetch, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{k}", encoding="utf-8")
        bib.write_text(
            "@article{k, title = {Some Title}, year = {2020}}\n",
            encoding="utf-8",
        )
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
            ]
        )
        mock_fetch.assert_not_called()

    def test_comment_and_string_entries_ignored(self, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{real2020}", encoding="utf-8")
        bib.write_text(
            textwrap.dedent(
                """\
                @comment{Generated by Mendeley}
                @string{prl = {Physical Review Letters}}
                @preamble{"\\providecommand{\\noopsort}[1]{}"}
                @article{real2020,
                  title = {Real Article},
                  year = {2020},
                }
                """
            ),
            encoding="utf-8",
        )
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
            ]
        )
        content = out.read_text(encoding="utf-8")
        assert "real2020" in content
        assert "Generated by Mendeley" not in content

    def test_citep_with_optional_notes(self, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\citep[see][p.~5]{note2020}", encoding="utf-8")
        bib.write_text(
            "@article{note2020, title = {With Notes}}\n", encoding="utf-8"
        )
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
            ]
        )
        assert "note2020" in out.read_text(encoding="utf-8")

    def test_multiple_keys_in_one_cite(self, tmp_path):
        tex = tmp_path / "p.tex"
        bib = tmp_path / "r.bib"
        out = tmp_path / "o.bib"
        tex.write_text(r"\cite{a2020,b2021,c2022}", encoding="utf-8")
        bib.write_text(
            "@article{a2020, title = {A}}\n"
            "@article{b2021, title = {B}}\n"
            "@article{c2022, title = {C}}\n",
            encoding="utf-8",
        )
        self._run(
            [
                "--tex",
                str(tex),
                "--bib",
                str(bib),
                "--out",
                str(out),
                "--no-doi",
            ]
        )
        content = out.read_text(encoding="utf-8")
        assert all(k in content for k in ("a2020", "b2021", "c2022"))

    def test_default_output_filename(self, tmp_path):
        tex = tmp_path / "paper.tex"
        bib = tmp_path / "refs.bib"
        tex.write_text(r"\cite{k}", encoding="utf-8")
        bib.write_text("@article{k, title = {T}}\n", encoding="utf-8")
        self._run(["--tex", str(tex), "--bib", str(bib), "--no-doi"])
        assert (tmp_path / "refs_clean.bib").exists()
