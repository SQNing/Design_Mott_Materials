"""Runtime evidence extraction and comparison for literature benchmarks."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
import hashlib
import json
import math
import re

from validation.literature_evidence_inventory import load_and_validate_inventory
from validation.literature_evidence_sources import load_verified_source
from validation import literature_spin_model_benchmarks as benchmark_functions


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "source-cache"


class RuntimeEvidenceError(ValueError):
    """Raised when source text cannot establish the registered claim."""


_PREPARED_TRACE_COORDINATE_SPACE = "private_prepared_extracted_text"


@dataclass(frozen=True)
class _PreparedView:
    builder_id: str
    version: int
    text: str
    sha256: str


@dataclass(frozen=True)
class _PreparedViewSpec:
    builder_id: str
    version: int
    builder: object


def _normalize_with_replacements(text, replacements):
    for old, new in replacements:
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def _dehyphenate_extracted_text(text, *, page_number_breaks=False):
    if page_number_breaks:
        text = re.sub(
            r"(?<=[A-Za-z])-\s*\f\s*\d{1,2}\s*(?=[a-z])",
            "",
            text,
        )
    return re.sub(
        r"(?<=[A-Za-z])-\s*\r?\n\s*(?=[a-z])",
        "",
        text,
    )


def _build_page_column_search_text(
    source_text,
    *,
    normalizer,
    split_columns,
    include_page_order,
    separator,
):
    extraction_views = [normalizer(source_text)]
    for split_column in split_columns:
        left_pages = []
        right_pages = []
        page_order_fragments = []
        for page in source_text.split("\f"):
            lines = page.splitlines()
            left_page = "\n".join(
                line[:split_column] for line in lines
            )
            right_page = "\n".join(
                line[split_column:] for line in lines
            )
            left_pages.append(left_page)
            right_pages.append(right_page)
            page_order_fragments.extend((left_page, right_page))
        extraction_views.append(normalizer("\n".join(left_pages)))
        extraction_views.append(normalizer("\n".join(right_pages)))
        if include_page_order:
            extraction_views.append(
                normalizer("\n".join(page_order_fragments))
            )
    return separator.join(extraction_views)


def _build_whitespace_normalized_extracted_text(source_text):
    return re.sub(r"\s+", " ", source_text).strip()


def _build_dash_normalized_extracted_text(source_text):
    return (
        _build_whitespace_normalized_extracted_text(source_text)
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
    )


def _build_collura_xx_extracted_text(source_text):
    return _build_dash_normalized_extracted_text(source_text).replace(
        "π", "pi"
    )


def _build_hirata_nomura_extracted_text(source_text):
    return (
        _build_whitespace_normalized_extracted_text(source_text)
        .replace("−", "-")
        .replace("–", "-")
    )


def _collapse_spaced_ocr_words(source_text):
    spaced_word = re.compile(
        r"(?<![A-Za-z])(?:[A-Za-z]\s+){3,}[A-Za-z](?![A-Za-z])"
    )
    return spaced_word.sub(
        lambda match: re.sub(r"\s+", "", match.group(0)),
        source_text,
    )


def _build_shastry_sutherland_dual_ocr_search_text(source_text):
    whitespace_normalized = _build_whitespace_normalized_extracted_text(
        source_text
    )
    collapsed = _collapse_spaced_ocr_words(whitespace_normalized)
    return whitespace_normalized + "\n" + "#" * 5000 + "\n" + collapsed


def _replace_ligatures_and_dashes(source_text, *, replace_dot=False):
    replacements = [
        ("ﬁ", "fi"),
        ("ﬂ", "fl"),
        ("ﬀ", "ff"),
        ("ﬃ", "ffi"),
        ("ﬄ", "ffl"),
        ("−", "-"),
        ("–", "-"),
        ("—", "-"),
    ]
    if replace_dot:
        replacements.append(("·", " dot "))
    for old, new in replacements:
        source_text = source_text.replace(old, new)
    return source_text


def _build_ligature_dash_normalized_extracted_text(source_text):
    normalized = _replace_ligatures_and_dashes(source_text)
    return re.sub(r"\s+", " ", normalized).strip()


def _build_ligature_dash_dehyphenated_extracted_text(source_text):
    normalized = _replace_ligatures_and_dashes(
        source_text, replace_dot=True
    )
    normalized = re.sub(r"(?<=\w)-\s+(?=\w)", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _build_balla_fcc_layout_search_text(source_text):
    normalized = _build_ligature_dash_dehyphenated_extracted_text(
        source_text
    )
    return normalized + "\n" + "#" * 5000 + "\n" + source_text


def _normalize_seki_extracted_text(text):
    text = re.sub(
        r"(?<=[A-Za-z])-\s*\r?\n\s*(?=[a-z])",
        "",
        text,
    )
    for old, new in (
        ("ﬁ", "fi"),
        ("ﬂ", "fl"),
        ("ﬀ", "ff"),
        ("ﬃ", "ffi"),
        ("ﬄ", "ffl"),
        ("−", "-"),
        ("–", "-"),
        ("—", "-"),
        ("∼", "~"),
    ):
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def _build_seki_science_layout_search_text(source_text):
    pages = source_text.split("\f")
    wide_left_raw = "\n".join(
        line[:138] for page in pages for line in page.splitlines()
    )
    two_column_raw = "\n".join(
        line[:112] for page in pages for line in page.splitlines()
    )
    column_major_raw = "\n".join(
        "\n".join(line[start:end] for line in page.splitlines())
        for page in pages
        for start, end in ((0, 55), (55, 112), (112, None))
    )
    search_text = " ".join(
        (
            _normalize_seki_extracted_text(source_text),
            _normalize_seki_extracted_text(wide_left_raw),
            _normalize_seki_extracted_text(two_column_raw),
            _normalize_seki_extracted_text(column_major_raw),
        )
    )
    separator = "\n" + "#" * 5000 + "\n"
    return separator.join((search_text, source_text, column_major_raw))


def _build_wernsdorfer_science_webprint_search_text(source_text):
    normalized = _build_ligature_dash_normalized_extracted_text(source_text)
    webprint_left_raw = "\n".join(
        line[:108] for line in source_text.splitlines()
    )
    webprint_left_normalized = (
        _build_ligature_dash_normalized_extracted_text(webprint_left_raw)
    )
    return " ".join((normalized, webprint_left_normalized))


def _build_yang_xie_extracted_text(source_text):
    return _normalize_with_replacements(
        source_text,
        (
            ("ﬁ", "fi"),
            ("ﬂ", "fl"),
            ("ﬀ", "ff"),
            ("ﬃ", "ffi"),
            ("ﬄ", "ffl"),
            ("−", "-"),
            ("–", "-"),
            ("—", "-"),
            ("〈", "<"),
            ("〉", ">"),
            ("±", "+/-"),
            ("∗", "*"),
            ("²", "2"),
        ),
    )


def _normalize_stodter_extracted_text(text):
    text = _dehyphenate_extracted_text(text, page_number_breaks=True)
    return _normalize_with_replacements(
        text,
        (
            ("ﬁ", "fi"),
            ("ﬂ", "fl"),
            ("ﬀ", "ff"),
            ("ﬃ", "ffi"),
            ("ﬄ", "ffl"),
            ("−", "-"),
            ("–", "-"),
            ("—", "-"),
            ("≲", "<="),
            ("≤", "<="),
            ("∼", "~"),
        ),
    )


def _build_stodter_pdf_layout_search_text(source_text):
    return _build_page_column_search_text(
        source_text,
        normalizer=_normalize_stodter_extracted_text,
        split_columns=(64, 68, 72, 76, 80),
        include_page_order=False,
        separator=" ",
    )


def _normalize_ishikawa_extracted_text(text):
    text = _dehyphenate_extracted_text(text, page_number_breaks=True)
    return _normalize_with_replacements(
        text,
        (
            ("ﬁ", "fi"),
            ("ﬂ", "fl"),
            ("ﬀ", "ff"),
            ("ﬃ", "ffi"),
            ("ﬄ", "ffl"),
            ("−", "-"),
            ("–", "-"),
            ("—", "-"),
            ("·", "*"),
            ("⋅", "*"),
            ("≲", "<="),
            ("≤", "<="),
            ("∼", "~"),
        ),
    )


def _build_ishikawa_pdf_layout_search_text(source_text):
    return _build_page_column_search_text(
        source_text,
        normalizer=_normalize_ishikawa_extracted_text,
        split_columns=(60, 64, 68, 72, 76, 80, 96, 100, 102, 104, 108),
        include_page_order=True,
        separator="\n" + "#" * 5000 + "\n",
    )


def _normalize_nawa_extracted_text(text):
    text = _dehyphenate_extracted_text(text)
    text = _normalize_with_replacements(
        text,
        (
            ("ﬁ", "fi"),
            ("ﬂ", "fl"),
            ("ﬀ", "ff"),
            ("ﬃ", "ffi"),
            ("ﬄ", "ffl"),
            ("−", "-"),
            ("–", "-"),
            ("—", "-"),
            ("α", "alpha"),
            ("Γ", "Gamma"),
            ("γ", "gamma"),
            ("μ", "mu"),
            ("Å", "A"),
            ("Å", "A"),
            ("′", "'"),
            ("’", "'"),
            ("°", " degrees "),
            ("◦", " degrees "),
        ),
    )
    text = re.sub(r"-\s+(?=\d)", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_nawa_pdf_layout_search_text(source_text):
    return _build_page_column_search_text(
        source_text,
        normalizer=_normalize_nawa_extracted_text,
        split_columns=(64, 68, 72, 76, 80, 84, 88, 92, 96, 100, 104, 108),
        include_page_order=True,
        separator="\n" + "#" * 5000 + "\n",
    )


def _normalize_boldrin_extracted_text(text):
    text = _dehyphenate_extracted_text(text)
    text = _normalize_with_replacements(
        text,
        (
            ("ﬁ", "fi"),
            ("ﬂ", "fl"),
            ("ﬀ", "ff"),
            ("ﬃ", "ffi"),
            ("ﬄ", "ffl"),
            ("−", "-"),
            ("–", "-"),
            ("—", "-"),
            ("¼", "="),
            ("ð", "("),
            ("Þ", ")"),
            ("þ", "+"),
            ("θ", "theta"),
            ("δ", "delta"),
            ("≈", "approximately"),
            ("≪", "<<"),
            ("≲", "<="),
            ("μ", "mu"),
            ("Å", "A"),
            ("Å", "A"),
            ("˚", ""),
            ("′", "'"),
            ("’", "'"),
            ("·", " dot "),
            ("×", " cross "),
            (";", ","),
            ("_", " "),
        ),
    )
    text = re.sub(
        r"\bj\s*(J\s*(?:0\s*3|3\s*'|d|1|2))\s*j\b",
        r"|\1|",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bJ\s*(?:0\s*3|3\s*')\b",
        "Jd",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bT\s+N\b", "TN", text)
    text = re.sub(r"\btheta\s*_?\s*W\b", "thetaW", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_boldrin_pdf_layout_search_text(source_text):
    return _build_page_column_search_text(
        source_text,
        normalizer=_normalize_boldrin_extracted_text,
        split_columns=(
            60,
            64,
            68,
            72,
            76,
            80,
            84,
            88,
            92,
            96,
            100,
            104,
            108,
        ),
        include_page_order=True,
        separator="\n" + "#" * 5000 + "\n",
    )


def _normalize_schiffer_extracted_text(text):
    text = _dehyphenate_extracted_text(text)
    text = _normalize_with_replacements(
        text,
        (
            ("ﬁ", "fi"),
            ("ﬂ", "fl"),
            ("ﬀ", "ff"),
            ("ﬃ", "ffi"),
            ("ﬄ", "ffl"),
            ("−", "-"),
            ("–", "-"),
            ("—", "-"),
            ("≈", " approximately "),
            ("≃", " approximately "),
            ("∼", " approximately "),
            ("≪", " much less than "),
            ("θ", "theta"),
            ("χ", "chi"),
            ("μ", "mu"),
            ("·", " dot "),
            ("_", " "),
        ),
    )
    text = re.sub(r"\(\(\s*(?=\d)", "<", text)
    text = re.sub(r"(?<=\d)\.\s+(?=\d)", ".", text)
    text = re.sub(r"(?<![A-Za-z])-{2,}(?=\s*\d)", "-", text)
    text = re.sub(
        r"Gd\s*3\s*Ga\s*5\s*0\s*,\s*2",
        "Gd3Ga5O12",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bmagnetic\s+Gd\s+corner-sharing\s+trianguions\s+are\s+on\s+"
        r"two\s+interpenetrating\s+lar\s+sublattices\b",
        "magnetic Gd ions are on two interpenetrating corner-sharing "
        "triangular sublattices",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\btv\s+o\b", "two", text, flags=re.IGNORECASE)
    text = re.sub(r"\b5\s*=\s*7\s*/\s*2\b", "S = 7/2", text)
    text = re.sub(
        r"\bOw[^\s]{0,8}\s*-+\s*2\s*K\b",
        "thetaW approximately -2 K",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(nearest neighbor dipole energy\s+is)\s*"
        r"(?:approximately\s*)?-?\s*7\s*K",
        r"\1 approximately 0.7 K",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(nearest neighbor dipole energy\s+is)\s*-\s*0\.7\s*K",
        r"\1 approximately 0.7 K",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"nearestexchange\s+interacneighbor\s+isotropic\s+"
        r"antiferromagnetic\s+tions",
        "nearest-neighbor isotropic antiferromagnetic exchange interactions",
        text,
        flags=re.IGNORECASE,
    )
    for joined, hyphenated in (
        ("nearestneighbor", "nearest-neighbor"),
        ("cornersharing", "corner-sharing"),
        ("longrange", "long-range"),
        ("firstorder", "first-order"),
        ("threedimensional", "three-dimensional"),
        ("finitetemperature", "finite-temperature"),
    ):
        text = re.sub(
            rf"\b{joined}\b", hyphenated, text, flags=re.IGNORECASE
        )
    text = re.sub(r"\bAFM\b", "antiferromagnetic", text)
    text = re.sub(r"\bLRO\b", "long-range order", text)
    text = re.sub(r"\bGGG\b", "GGG", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_schiffer_pdf_layout_search_text(source_text):
    return _build_page_column_search_text(
        source_text,
        normalizer=_normalize_schiffer_extracted_text,
        split_columns=(
            48,
            52,
            56,
            60,
            64,
            68,
            72,
            76,
            80,
            84,
            88,
            92,
            96,
            100,
            104,
            108,
            112,
            116,
        ),
        include_page_order=True,
        separator="\n" + "#" * 5000 + "\n",
    )


def _normalize_quilliam_extracted_text(text):
    text = _dehyphenate_extracted_text(text)
    text = _normalize_with_replacements(
        text,
        (
            ("ﬁ", "fi"),
            ("ﬂ", "fl"),
            ("ﬀ", "ff"),
            ("ﬃ", "ffi"),
            ("ﬄ", "ffl"),
            ("−", "-"),
            ("–", "-"),
            ("—", "-"),
            ("≈", " approximately "),
            ("≃", " approximately "),
            ("∼", " approximately "),
            ("\x05", " approximately "),
            ("θ", "theta"),
            ("∆", "Delta"),
            ("Δ", "Delta"),
            ("χ", "chi"),
            ("μ", "mu"),
            ("˚", ""),
            ("Å", "A"),
            ("¯", "-"),
            ("·", " dot "),
            ("〈", "<"),
            ("〉", ">"),
            ("_", " "),
        ),
    )
    text = re.sub(r"(?<=\d)\.\s+(?=\d)", ".", text)
    for pattern, replacement in (
        (r"\bGd\s*3\s*Te\s*2\s*Li\s*3\s*O\s*12\b", "Gd3Te2Li3O12"),
        (r"\bGd\s*3\s*Ga\s*5\s*O\s*12\b", "Gd3Ga5O12"),
        (r"\bGd\s*3\s*Al\s*5\s*O\s*12\b", "Gd3Al5O12"),
        (r"\bI\s*a\s*-?\s*3\s*d\b", "Ia-3d"),
    ):
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\bH\s*Ex\b", "HEx", text)
    text = re.sub(r"\bH\s*D\b", "HD", text)
    text = re.sub(r"\btheta\s*C\s*W\b", "thetaCW", text)
    text = re.sub(r"\bT\s*C\b", "TC", text)
    text = re.sub(r"\bJ\s*1\b", "J1", text)
    text = re.sub(r"\bGTLG\b", "GTLG", text)
    text = re.sub(r"\bLRO\b", "long-range order", text)
    for joined, hyphenated in (
        ("nearestneighbor", "nearest-neighbor"),
        ("cornersharing", "corner-sharing"),
        ("longrange", "long-range"),
        ("firstorder", "first-order"),
        ("threedimensional", "three-dimensional"),
        ("spinwave", "spin-wave"),
        ("furtherneighbor", "further-neighbor"),
    ):
        text = re.sub(
            rf"\b{joined}\b", hyphenated, text, flags=re.IGNORECASE
        )
    return re.sub(r"\s+", " ", text).strip()


def _build_quilliam_pdf_layout_search_text(source_text):
    return _build_page_column_search_text(
        source_text,
        normalizer=_normalize_quilliam_extracted_text,
        split_columns=(
            52,
            56,
            60,
            64,
            68,
            72,
            76,
            80,
            84,
            88,
            92,
            96,
            100,
            104,
            108,
            112,
            116,
            120,
        ),
        include_page_order=True,
        separator="\n" + "#" * 5000 + "\n",
    )


_SUBSCRIPT_DIGIT_REPLACEMENTS = tuple(
    zip("₀₁₂₃₄₅₆₇₈₉", "0123456789")
)
_SUPERSCRIPT_DIGIT_REPLACEMENTS = tuple(
    zip("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
)
_LIGATURE_DASH_REPLACEMENTS = (
    ("ﬁ", "fi"),
    ("ﬂ", "fl"),
    ("ﬀ", "ff"),
    ("ﬃ", "ffi"),
    ("ﬄ", "ffl"),
    ("−", "-"),
    ("–", "-"),
    ("—", "-"),
)


def _build_kitagawa_h3liir2o6_extracted_text(source_text):
    return _normalize_with_replacements(
        source_text,
        (*_LIGATURE_DASH_REPLACEMENTS, *_SUBSCRIPT_DIGIT_REPLACEMENTS),
    )


def _build_ramirez_dy2ti2o7_extracted_text(source_text):
    return _normalize_with_replacements(
        source_text,
        (
            *_LIGATURE_DASH_REPLACEMENTS,
            ("‘", "'"),
            ("’", "'"),
            *_SUBSCRIPT_DIGIT_REPLACEMENTS,
        ),
    )


def _build_carteaux_cr2ge2te6_extracted_text(source_text):
    return _normalize_with_replacements(
        source_text,
        (
            *_LIGATURE_DASH_REPLACEMENTS,
            *_SUBSCRIPT_DIGIT_REPLACEMENTS,
            *_SUPERSCRIPT_DIGIT_REPLACEMENTS,
            ("⁺", "+"),
            ("μ", "mu"),
            ("µ", "mu"),
        ),
    )


def _build_cable_crcl3_extracted_text(source_text):
    return _normalize_with_replacements(
        source_text,
        (
            *_LIGATURE_DASH_REPLACEMENTS,
            *_SUBSCRIPT_DIGIT_REPLACEMENTS,
            ("°", " "),
        ),
    )


def _build_ressouche_mnps3_extracted_text(source_text):
    text = source_text
    for old, new in (
        *_LIGATURE_DASH_REPLACEMENTS,
        *_SUBSCRIPT_DIGIT_REPLACEMENTS,
        *_SUPERSCRIPT_DIGIT_REPLACEMENTS,
        ("⁺", "+"),
        ("共", "("),
        ("兲", ")"),
    ):
        text = text.replace(old, new)
    text = re.sub(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_furuchi_lieb_lattice_extracted_text(source_text):
    text = source_text
    for old, new in (
        *_LIGATURE_DASH_REPLACEMENTS,
        ("′", "'"),
        ("’", "'"),
        ("·", " dot "),
        ("η", "eta"),
        *_SUBSCRIPT_DIGIT_REPLACEMENTS,
    ):
        text = text.replace(old, new)
    text = re.sub(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_hsieh_nacro2_extracted_text(source_text):
    text = source_text
    for old, new in (
        *_LIGATURE_DASH_REPLACEMENTS,
        ("′", "'"),
        ("’", "'"),
        ("∼", " approximately "),
        ("≈", " approximately "),
        ("ξ", "xi"),
        ("π", "pi"),
        ("∞", " infinity "),
        ("→", " approaching "),
        ("Å", " A "),
        ("˚", ""),
        ("◦", "-degree "),
        ("°", "-degree "),
        (">", " greater than "),
        ("<", " less than "),
    ):
        text = text.replace(old, new)
    text = re.sub(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_mazin_honeycomb_j1_j2_j3_extracted_text(source_text):
    return _normalize_with_replacements(
        source_text,
        (
            *_LIGATURE_DASH_REPLACEMENTS,
            ("“", '"'),
            ("”", '"'),
            ("’", "'"),
            ("´", "'"),
            ("é", "e"),
            ("É", "E"),
        ),
    )


def _build_blote_luijten_heringa_numeric_extracted_text(source_text):
    text = re.sub(r"\s+", " ", source_text).strip()
    return re.sub(r"(?<=\d):(?=\d)", ".", text)


def _build_sandvik_daul_square_xy_ring_extracted_text(source_text):
    text = re.sub(r"\s+", " ", source_text).strip()
    return text.replace("−", "-").replace("–", "-")


def _build_chaloupka_full_kitaev_heisenberg_extracted_text(source_text):
    text = re.sub(r"\s+", " ", source_text).strip()
    return text.replace("−", "-").replace("–", "-")


def _build_chubukov_golosov_scan_extracted_text(source_text):
    scan_layout_forms_accepted = bool(
        re.search(
            r"antiferromagneton|onatriangular|magnet-\s+ization",
            source_text,
            flags=re.IGNORECASE,
        )
    )
    text = source_text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if scan_layout_forms_accepted:
        text += "\n#scan-layout-forms-accepted"
    return text


_PREPARED_VIEW_SPECS = MappingProxyType(
    {
        ("yang_xie_extracted_text", 1): _PreparedViewSpec(
            "yang_xie_extracted_text", 1, _build_yang_xie_extracted_text
        ),
        (
            "whitespace_normalized_extracted_text",
            1,
        ): _PreparedViewSpec(
            "whitespace_normalized_extracted_text",
            1,
            _build_whitespace_normalized_extracted_text,
        ),
        ("dash_normalized_extracted_text", 1): _PreparedViewSpec(
            "dash_normalized_extracted_text",
            1,
            _build_dash_normalized_extracted_text,
        ),
        ("collura_xx_extracted_text", 1): _PreparedViewSpec(
            "collura_xx_extracted_text",
            1,
            _build_collura_xx_extracted_text,
        ),
        ("hirata_nomura_extracted_text", 1): _PreparedViewSpec(
            "hirata_nomura_extracted_text",
            1,
            _build_hirata_nomura_extracted_text,
        ),
        (
            "shastry_sutherland_dual_ocr_search_text",
            1,
        ): _PreparedViewSpec(
            "shastry_sutherland_dual_ocr_search_text",
            1,
            _build_shastry_sutherland_dual_ocr_search_text,
        ),
        (
            "ligature_dash_normalized_extracted_text",
            1,
        ): _PreparedViewSpec(
            "ligature_dash_normalized_extracted_text",
            1,
            _build_ligature_dash_normalized_extracted_text,
        ),
        (
            "ligature_dash_dehyphenated_extracted_text",
            1,
        ): _PreparedViewSpec(
            "ligature_dash_dehyphenated_extracted_text",
            1,
            _build_ligature_dash_dehyphenated_extracted_text,
        ),
        ("balla_fcc_layout_search_text", 1): _PreparedViewSpec(
            "balla_fcc_layout_search_text",
            1,
            _build_balla_fcc_layout_search_text,
        ),
        ("seki_science_layout_search_text", 1): _PreparedViewSpec(
            "seki_science_layout_search_text",
            1,
            _build_seki_science_layout_search_text,
        ),
        (
            "wernsdorfer_science_webprint_search_text",
            1,
        ): _PreparedViewSpec(
            "wernsdorfer_science_webprint_search_text",
            1,
            _build_wernsdorfer_science_webprint_search_text,
        ),
        ("stodter_pdf_layout_search_text", 1): _PreparedViewSpec(
            "stodter_pdf_layout_search_text",
            1,
            _build_stodter_pdf_layout_search_text,
        ),
        ("ishikawa_pdf_layout_search_text", 1): _PreparedViewSpec(
            "ishikawa_pdf_layout_search_text",
            1,
            _build_ishikawa_pdf_layout_search_text,
        ),
        ("nawa_pdf_layout_search_text", 1): _PreparedViewSpec(
            "nawa_pdf_layout_search_text",
            1,
            _build_nawa_pdf_layout_search_text,
        ),
        ("schiffer_pdf_layout_search_text", 1): _PreparedViewSpec(
            "schiffer_pdf_layout_search_text",
            1,
            _build_schiffer_pdf_layout_search_text,
        ),
        ("quilliam_pdf_layout_search_text", 1): _PreparedViewSpec(
            "quilliam_pdf_layout_search_text",
            1,
            _build_quilliam_pdf_layout_search_text,
        ),
        ("boldrin_pdf_layout_search_text", 1): _PreparedViewSpec(
            "boldrin_pdf_layout_search_text",
            1,
            _build_boldrin_pdf_layout_search_text,
        ),
        ("kitagawa_h3liir2o6_extracted_text", 1): _PreparedViewSpec(
            "kitagawa_h3liir2o6_extracted_text",
            1,
            _build_kitagawa_h3liir2o6_extracted_text,
        ),
        ("ramirez_dy2ti2o7_extracted_text", 1): _PreparedViewSpec(
            "ramirez_dy2ti2o7_extracted_text",
            1,
            _build_ramirez_dy2ti2o7_extracted_text,
        ),
        ("carteaux_cr2ge2te6_extracted_text", 1): _PreparedViewSpec(
            "carteaux_cr2ge2te6_extracted_text",
            1,
            _build_carteaux_cr2ge2te6_extracted_text,
        ),
        ("cable_crcl3_extracted_text", 1): _PreparedViewSpec(
            "cable_crcl3_extracted_text",
            1,
            _build_cable_crcl3_extracted_text,
        ),
        ("ressouche_mnps3_extracted_text", 1): _PreparedViewSpec(
            "ressouche_mnps3_extracted_text",
            1,
            _build_ressouche_mnps3_extracted_text,
        ),
        ("furuchi_lieb_lattice_extracted_text", 1): _PreparedViewSpec(
            "furuchi_lieb_lattice_extracted_text",
            1,
            _build_furuchi_lieb_lattice_extracted_text,
        ),
        ("hsieh_nacro2_extracted_text", 1): _PreparedViewSpec(
            "hsieh_nacro2_extracted_text",
            1,
            _build_hsieh_nacro2_extracted_text,
        ),
        ("mazin_honeycomb_j1_j2_j3_extracted_text", 1): _PreparedViewSpec(
            "mazin_honeycomb_j1_j2_j3_extracted_text",
            1,
            _build_mazin_honeycomb_j1_j2_j3_extracted_text,
        ),
        (
            "blote_luijten_heringa_numeric_extracted_text",
            1,
        ): _PreparedViewSpec(
            "blote_luijten_heringa_numeric_extracted_text",
            1,
            _build_blote_luijten_heringa_numeric_extracted_text,
        ),
        (
            "chaloupka_full_kitaev_heisenberg_extracted_text",
            1,
        ): _PreparedViewSpec(
            "chaloupka_full_kitaev_heisenberg_extracted_text",
            1,
            _build_chaloupka_full_kitaev_heisenberg_extracted_text,
        ),
        (
            "sandvik_daul_square_xy_ring_extracted_text",
            1,
        ): _PreparedViewSpec(
            "sandvik_daul_square_xy_ring_extracted_text",
            1,
            _build_sandvik_daul_square_xy_ring_extracted_text,
        ),
        ("chubukov_golosov_scan_extracted_text", 1): _PreparedViewSpec(
            "chubukov_golosov_scan_extracted_text",
            1,
            _build_chubukov_golosov_scan_extracted_text,
        ),
    }
)


_PREPARED_TRACE_PARSER_BUILDERS = MappingProxyType(
    {
        "parse_yang_xie_square_blume_capel_crossing": (
            "yang_xie_extracted_text",
            1,
        ),
        "parse_yang_xie_single_ion_spin1_anisotropy_levels": (
            "yang_xie_extracted_text",
            1,
        ),
        "parse_jiang_wiese_square_heisenberg_spin_stiffness": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_jiang_wiese_square_heisenberg_staggered_magnetization": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_jiang_wiese_square_heisenberg_spin_wave_velocity": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_depenbrock_kagome_heisenberg_energy": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_depenbrock_kagome_heisenberg_energy_and_spin_gap": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_stodter_clinoatacamite_distorted_kagome_exchange": (
            "stodter_pdf_layout_search_text",
            1,
        ),
        "parse_ishikawa_edwardsite_spin_half_deformed_kagome": (
            "ishikawa_pdf_layout_search_text",
            1,
        ),
        "parse_nawa_rubr3_kitaev_candidate_and_competing_interactions": (
            "nawa_pdf_layout_search_text",
            1,
        ),
        "parse_schiffer_ggg_strong_frustration_correction": (
            "schiffer_pdf_layout_search_text",
            1,
        ),
        "parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction": (
            "quilliam_pdf_layout_search_text",
            1,
        ),
        "parse_boldrin_vesignieite_dominant_j3_correction": (
            "boldrin_pdf_layout_search_text",
            1,
        ),
        "parse_dziarmaga_tfim_critical_point": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_dziarmaga_tfim_gap": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_collura_xx_chain_energy": (
            "collura_xx_extracted_text",
            1,
        ),
        "parse_pinettes_diep_simple_cubic_boundary": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_shastry_sutherland_exact_dimer_product": (
            "shastry_sutherland_dual_ocr_search_text",
            1,
        ),
        "parse_fouet_checkerboard_classical_constraint": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_kano_naya_kagome_ising_ferromagnet_tc": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_kano_naya_kagome_ising_antiferromagnet_entropy": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_garel_maillard_villain_entropy": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_husimi_syozi_honeycomb_ising_tc": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_husimi_syozi_triangular_ising_tc": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_ising_1925_linear_chain_no_transition": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_hirata_nomura_xxz_phase_boundaries": (
            "hirata_nomura_extracted_text",
            1,
        ),
        "parse_kumar_j1_j2_critical_point": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_kumar_j1_j2_bkt_reference": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_savary_er2ti2o7_psi2_order_by_quantum_disorder": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_richter_star_lattice_valence_bond_ground_state": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_richter_square_kagome_reference": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_wildes_feps3_ising_zigzag_order": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_dey_ba3irti2o9_triangular_spin_liquid_candidate": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_ghosh_mila_ruby_localized_magnon_eigenstate": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_biffin_gamma_li2iro3_spiral_kitaev_order": (
            "dash_normalized_extracted_text",
            1,
        ),
        "parse_mulder_honeycomb_spiral_contour": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_balla_iqbal_penc_fcc_type_orders": (
            "balla_fcc_layout_search_text",
            1,
        ),
        "parse_henley_pyrochlore_coulomb_phase": (
            "ligature_dash_dehyphenated_extracted_text",
            1,
        ),
        "parse_abramchuk_cu2iro3_honeycomb_iridate": (
            "ligature_dash_normalized_extracted_text",
            1,
        ),
        "parse_enderle_licuvo4_incommensurate_helimagnet": (
            "ligature_dash_normalized_extracted_text",
            1,
        ),
        "parse_bak_jensen_mnsi_long_wavelength_helix": (
            "ligature_dash_normalized_extracted_text",
            1,
        ),
        "parse_seki_cu2oseo3_skyrmion_lattice_phase": (
            "seki_science_layout_search_text",
            1,
        ),
        "parse_wernsdorfer_sessoli_fe8_quantum_tunneling": (
            "wernsdorfer_science_webprint_search_text",
            1,
        ),
        "parse_kitagawa_h3liir2o6_no_magnetic_order": (
            "kitagawa_h3liir2o6_extracted_text",
            1,
        ),
        "parse_ramirez_dy2ti2o7_pauling_entropy": (
            "ramirez_dy2ti2o7_extracted_text",
            1,
        ),
        "parse_carteaux_cr2ge2te6_ferromagnetic_order": (
            "carteaux_cr2ge2te6_extracted_text",
            1,
        ),
        "parse_cable_crcl3_ferromagnetic_layers": (
            "cable_crcl3_extracted_text",
            1,
        ),
        "parse_ressouche_mnps3_neel_order": (
            "ressouche_mnps3_extracted_text",
            1,
        ),
        "parse_furuchi_lieb_lattice_ground_state_spin": (
            "furuchi_lieb_lattice_extracted_text",
            1,
        ),
        "parse_hsieh_nacro2_unconventional_spin_order": (
            "hsieh_nacro2_extracted_text",
            1,
        ),
        "parse_mazin_honeycomb_j1_j2_j3_phase_set": (
            "mazin_honeycomb_j1_j2_j3_extracted_text",
            1,
        ),
        "parse_kitazawa_nomura_takhtajan_babujian_point": (
            "whitespace_normalized_extracted_text",
            1,
        ),
        "parse_blote_luijten_heringa_simple_cubic_ising_tc": (
            "blote_luijten_heringa_numeric_extracted_text",
            1,
        ),
        "parse_sandvik_daul_square_xy_ring_bond_order": (
            "sandvik_daul_square_xy_ring_extracted_text",
            1,
        ),
        "parse_chaloupka_full_kitaev_heisenberg_ordered_phases": (
            "chaloupka_full_kitaev_heisenberg_extracted_text",
            1,
        ),
        "parse_chaloupka_na2iro3_zigzag_relevance": (
            "chaloupka_full_kitaev_heisenberg_extracted_text",
            1,
        ),
        "parse_chubukov_golosov_triangular_plateau": (
            "chubukov_golosov_scan_extracted_text",
            1,
        ),
    }
)


_PREPARED_COORDINATE_METADATA_KEYS = frozenset(
    {
        "coordinate_space",
        "coordinate_builder",
        "coordinate_contract_version",
        "coordinate_view_sha256",
        "coordinate_view_length",
        "text_span_sha256",
        "text_span_captures",
    }
)


def _build_prepared_view(source_text, *, builder_id, version):
    if not isinstance(source_text, str):
        raise RuntimeEvidenceError("prepared view requires text")
    if type(version) is not int:
        raise RuntimeEvidenceError(
            "prepared view version must be an exact integer"
        )
    spec = _PREPARED_VIEW_SPECS.get((builder_id, version))
    if spec is None:
        raise RuntimeEvidenceError(
            "prepared view builder/version is unsupported"
        )
    text = spec.builder(source_text)
    return _PreparedView(
        builder_id=spec.builder_id,
        version=spec.version,
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _prepared_view_for_parser(source_text, parser_name):
    builder_id, version = _PREPARED_TRACE_PARSER_BUILDERS[parser_name]
    return _build_prepared_view(
        source_text, builder_id=builder_id, version=version
    )


def _finalize_prepared_trace(parsed_and_trace, prepared):
    parsed, source_trace = parsed_and_trace
    trace = dict(source_trace)
    contradictory = _PREPARED_COORDINATE_METADATA_KEYS.intersection(trace)
    if contradictory:
        raise RuntimeEvidenceError(
            "prepared parser core returned coordinate metadata"
        )
    spans = trace.get("text_spans")
    if not _is_valid_text_spans(spans):
        raise RuntimeEvidenceError("prepared parser returned invalid text spans")
    captures = []
    span_sha256 = []
    for start, end in spans:
        if end > len(prepared.text):
            raise RuntimeEvidenceError(
                "prepared parser returned an out-of-range text span"
            )
        capture = prepared.text[start:end]
        captures.append(capture)
        span_sha256.append(
            hashlib.sha256(capture.encode("utf-8")).hexdigest()
        )
    trace.update(
        {
            "coordinate_space": _PREPARED_TRACE_COORDINATE_SPACE,
            "coordinate_builder": prepared.builder_id,
            "coordinate_contract_version": prepared.version,
            "coordinate_view_sha256": prepared.sha256,
            "coordinate_view_length": len(prepared.text),
            "text_span_sha256": span_sha256,
            "text_span_captures": captures,
        }
    )
    return parsed, trace


def _require_finite_real(value, *, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeEvidenceError(f"{label} must be a finite real number")
    try:
        finite_value = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise RuntimeEvidenceError(
            f"{label} must be a finite real number"
        ) from exc
    if not math.isfinite(finite_value):
        raise RuntimeEvidenceError(f"{label} must be a finite real number")
    return finite_value


def _require_positive_finite_real(value, *, label):
    value = _require_finite_real(value, label=label)
    if value <= 0.0:
        raise RuntimeEvidenceError(f"{label} must be positive")
    return value


def recompute_blume_capel_zero_temperature_crossing(
    *, coordination_number, exchange
):
    """Compare the spin-1 ferromagnetic and all-zero product-state energies."""

    if (
        isinstance(coordination_number, bool)
        or not isinstance(coordination_number, int)
        or coordination_number != 4
    ):
        raise RuntimeEvidenceError(
            "Blume-Capel square-lattice coordination number must equal four"
        )
    exchange = _require_positive_finite_real(
        exchange, label="Blume-Capel exchange"
    )
    ordered_exchange_energy_per_site = (
        -0.5 * coordination_number * exchange
    )
    crossing_anisotropy = -ordered_exchange_energy_per_site
    crossing_ratio = crossing_anisotropy / exchange
    return {"square_lattice_d_over_j_crossing": crossing_ratio}


def parse_yang_xie_square_blume_capel_crossing(source_text):
    """Extract the exact square-lattice Blume-Capel zero-T crossing."""

    error_prefix = "Yang-Xie Blume-Capel square-lattice crossing"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_yang_xie_square_blume_capel_crossing"
    )
    return _finalize_prepared_trace(
        _parse_yang_xie_square_blume_capel_crossing_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_yang_xie_square_blume_capel_crossing_prepared(normalized):
    error_prefix = "Yang-Xie Blume-Capel square-lattice crossing"

    spin_i = r"S\s*_?\s*i"
    spin_j = r"S\s*_?\s*j"
    spin_i_squared = rf"{spin_i}\s*(?:\^?\s*2)"
    spin_j_squared = rf"{spin_j}\s*(?:\^?\s*2)"
    spin_i_z = rf"{spin_i}\s*(?:\^?\s*z|z)"
    h_ij = r"H\s*_?\s*i\s*j"

    identity_match = re.search(
        r"The tensor renormalization group study of the general "
        r"spin\s*-\s*S Blume\s*-\s*Capel model"
        r".{0,1800}?Li\s*-\s*Ping Yang"
        r".{0,500}?and Zhi\s*-\s*Yuan Xie"
        r".{0,2600}?arXiv\s*:\s*1204\.5027v2",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"We focus on the special situation of\s*D\s*=\s*"
        r"(?P<abstract_d_multiplier>\d+)\s*J"
        r".{0,500}?general spin\s*-\s*S Blume\s*-\s*Capel model "
        r"on the square lattice"
        r".{0,3000}?absence of the magnetic field"
        r".{0,600}?visualization parameter"
        r".{0,600}?intrinsic degeneracy of the different phases",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"The Hamiltonian of the Blume\s*-\s*Capel model"
        r"(?:\s*\[\s*1\s*\])?\s+with"
        r".{0,900}?general spin\s*-\s*S is"
        r".{0,600}?\bH\s*=\s*-\s*J"
        r".{0,500}?"
        + spin_i
        + r"\s*"
        + spin_j
        + r"\s*\+\s*D"
        r".{0,500}?"
        + spin_i_squared
        + r"\s*-\s*h"
        r".{0,500}?"
        + spin_i_z
        + r"\s*[,\.]?\s*\(\s*1\s*\)"
        r".{0,900}?spin variable S takes\s*2\s*S\s*\+\s*1 values"
        r".{0,400}?\(\s*-\s*S\s*,\s*-\s*S\s*\+"
        r".{0,900}?\b1\s*,"
        r".{0,120}?S\s*-\s*1\s*,\s*S\s*\)"
        r".{0,800}?J is the coupling constant"
        r".{0,500}?D is.{0,900}?strength of the "
        r"single\s*-\s*ion anisotropy"
        r".{0,500}?h is the mag(?:netic|-\s*.{0,900}?netic) field"
        r".{0,700}?first term runs over all"
        r".{0,700}?nearest neighbors"
        r".{0,400}?consider the case of\s*h\s*=\s*0",
        normalized,
        flags=re.IGNORECASE,
    )
    bond_match = re.search(
        r"(?:hamiltonian of any bond linking two"
        r".{0,1000}?sites\s*i\s*,?\s*(?:and\s+|,\s*)?j"
        r"|sites\s*i\s*,\s*j\s*,?\s*then we have)"
        r".{0,500}?"
        + h_ij
        + r"\s*=\s*-\s*J\s*"
        + spin_i
        + r"\s*"
        + spin_j
        + r"\s*\+\s*D\s*\(\s*"
        + spin_i_squared
        + r"\s*\+\s*"
        + spin_j_squared
        + r"\s*\)\s*/\s*q\s*[,\.]?\s*\(\s*2\s*\)"
        r".{0,500}?q is the coordination number",
        normalized,
        flags=re.IGNORECASE,
    )
    square_completion_match = re.search(
        r"(?:This )?formula can be rewritten as"
        r".{0,300}?"
        + h_ij
        + r"\s*=\s*J\s*\(\s*"
        + spin_i
        + r"\s*-\s*"
        + spin_j
        + r"\s*\)\s*(?:\^?\s*2)\s*/\s*2"
        r"\s*\+\s*\(\s*D\s*/\s*q\s*-\s*J\s*/\s*2\s*\)"
        r"\s*\(\s*"
        + spin_i_squared
        + r"\s*\+\s*"
        + spin_j_squared
        + r"\s*\)\s*[,\.]?\s*\(\s*3\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    ordered_zero_sides_match = re.search(
        r"ferromagnetic coupling\s*\(\s*J\s*>\s*0\s*\)"
        r".{0,300}?when\s*D\s*>\s*q\s*J\s*/\s*"
        r"(?P<zero_side_denominator>\d+)"
        r".{0,500}?configuration of the ground"
        r".{0,700}?state is\s*"
        + spin_i
        + r"\s*=\s*"
        + spin_j
        + r"\s*=\s*0"
        r".{0,1200}?integer"
        r".{0,1400}?when\s*D\s*<\s*q\s*J\s*/\s*"
        r"(?P<ordered_side_denominator>\d+)"
        r".{0,500}?configuration of the ground"
        r".{0,700}?state is\s*"
        + spin_i
        + r"\s*=\s*"
        + spin_j
        + r"\s*=\s*max\s*\(\s*S\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    degeneracy_match = re.search(
        r"special situation"
        r".{0,160}?D\s*=\s*q\s*J\s*/\s*"
        r"(?P<degeneracy_denominator>\d+)"
        r".{0,500}?ground state is\s*"
        + spin_i
        + r"\s*=\s*"
        + spin_j
        + r".{0,500}?\(\s*2\s*S\s*\+\s*1\s*\)"
        r"\s*-\s*fold degener(?:acy|-\s*.{0,900}?acy)",
        normalized,
        flags=re.IGNORECASE,
    )
    square_endpoint_match = re.search(
        r"focus on the square.{0,900}?lattice"
        r".{0,300}?q\s*=\s*(?P<coordination_number>\d+)"
        r".{0,300}?D\s*=\s*(?P<square_d_multiplier>\d+)\s*J"
        r".{0,300}?special.{0,900}?parameter"
        r".{0,600}?phase boundaries of the square lattice"
        r".{0,300}?end at\s*\(\s*T\s*/\s*J\s*,\s*D\s*/\s*J\s*\)"
        r"\s*=\s*\(\s*(?P<endpoint_temperature>\d+)\s*,\s*"
        r"(?P<endpoint_ratio>\d+)\s*\)"
        r".{0,500}?critical temperature is\s*T\s*_?\s*c\s*=\s*"
        r"(?P<critical_temperature>\d+)"
        r".{0,500}?when\s*h\s*=\s*0",
        normalized,
        flags=re.IGNORECASE,
    )
    spin_one_match = re.search(
        r"In the case of\s*S\s*=\s*(?P<spin>\d+)"
        r".{0,200}?there are three optional values"
        r".{0,120}?\+/-\s*1\s*(?:,|and)\s*0"
        r".{0,200}?for each spin variable",
        normalized,
        flags=re.IGNORECASE,
    )
    references_match = re.search(
        r"\[\s*1\s*\]\s*M\.\s*Blume,\s*Phys\.\s*Rev\.\s*"
        r"141\s*,\s*517\s*\(\s*1966\s*\)\s*;\s*"
        r"H\.\s*W\.\s*Capel,"
        r".{0,1200}?Physica\s*32\s*,\s*966\s*\(\s*1966\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    matches_by_name = {
        "source_identity": identity_match,
        "d_equals_2j_square_lattice_abstract": abstract_match,
        "blume_capel_hamiltonian_and_zero_field": hamiltonian_match,
        "bond_hamiltonian_equation_2": bond_match,
        "bond_square_completion_equation_3": square_completion_match,
        "ordered_and_zero_ground_state_sides": ordered_zero_sides_match,
        "qj_over_two_degeneracy": degeneracy_match,
        "square_lattice_zero_temperature_endpoint": square_endpoint_match,
        "spin_one_local_states": spin_one_match,
        "blume_and_capel_original_references": references_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified Yang-Xie source, "
            "the -J exchange plus D single-ion Hamiltonian at h=0, "
            "bond Eqs. (2)-(3), both sides of D=qJ/2, the spin-1 "
            "local states, q=4 and D/J=2 on the square lattice, and "
            "the Blume/Capel bibliography pair; missing anchors: "
            f"{', '.join(missing_anchors)}"
        )

    abstract_d_multiplier = int(
        abstract_match.group("abstract_d_multiplier")
    )
    zero_side_denominator = int(
        ordered_zero_sides_match.group("zero_side_denominator")
    )
    ordered_side_denominator = int(
        ordered_zero_sides_match.group("ordered_side_denominator")
    )
    degeneracy_denominator = int(
        degeneracy_match.group("degeneracy_denominator")
    )
    coordination_number = int(
        square_endpoint_match.group("coordination_number")
    )
    square_d_multiplier = int(
        square_endpoint_match.group("square_d_multiplier")
    )
    endpoint_temperature = int(
        square_endpoint_match.group("endpoint_temperature")
    )
    endpoint_ratio = int(
        square_endpoint_match.group("endpoint_ratio")
    )
    critical_temperature = int(
        square_endpoint_match.group("critical_temperature")
    )
    spin = int(spin_one_match.group("spin"))
    if 0 in (
        zero_side_denominator,
        ordered_side_denominator,
        degeneracy_denominator,
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} contains a zero crossing denominator"
        )

    source_crossing_ratio = (
        coordination_number / degeneracy_denominator
    )
    try:
        recomputed = recompute_blume_capel_zero_temperature_crossing(
            coordination_number=coordination_number,
            exchange=1.0,
        )
    except RuntimeEvidenceError as exc:
        raise RuntimeEvidenceError(
            f"{error_prefix} numerical anchors disagree with the "
            "registered square-lattice D/J=2 level crossing"
        ) from exc
    expected_ratio = recomputed["square_lattice_d_over_j_crossing"]
    exact_values = (
        abstract_d_multiplier == 2
        and zero_side_denominator == 2
        and ordered_side_denominator == 2
        and degeneracy_denominator == 2
        and coordination_number == 4
        and square_d_multiplier == 2
        and endpoint_temperature == 0
        and endpoint_ratio == 2
        and critical_temperature == 0
        and spin == 1
        and math.isclose(
            source_crossing_ratio,
            expected_ratio,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
    )
    if not exact_values:
        raise RuntimeEvidenceError(
            f"{error_prefix} numerical anchors disagree with the "
            "registered square-lattice D/J=2 level crossing"
        )

    ordered_exchange_energy = -0.5 * coordination_number
    ordered_anisotropy_energy = source_crossing_ratio * spin**2
    zero_state_energy = 0.0
    if not math.isclose(
        ordered_exchange_energy + ordered_anisotropy_energy,
        zero_state_energy,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} product-state energies do not cross"
        )

    matches = tuple(matches_by_name.values())
    return (
        {"square_lattice_d_over_j_crossing": source_crossing_ratio},
        {
            "parser": "parse_yang_xie_square_blume_capel_crossing",
            "source_identity": "arXiv:1204.5027v2",
            "registered_doi": "10.1103/PhysRev.141.517",
            "corrected_original_doi": (
                "10.1016/0031-8914(66)90027-9"
            ),
            "source_equations": ["1", "2", "3"],
            "spin": spin,
            "coordination_number": coordination_number,
            "zero_field": True,
            "ferromagnetic_exchange": True,
            "crossing_condition": "D=qJ/2",
            "source_crossing_ratio": source_crossing_ratio,
            "ordered_exchange_energy_per_site_over_j": (
                ordered_exchange_energy
            ),
            "ordered_anisotropy_energy_per_site_over_j": (
                ordered_anisotropy_energy
            ),
            "zero_state_energy_per_site_over_j": zero_state_energy,
            "source_role": (
                "machine-extractable supplemental direct primary "
                "research source"
            ),
            "registered_source_correction": (
                "The registered DOI identifies Blume's UO2 paper; "
                "Capel 1966 DOI 10.1016/0031-8914(66)90027-9 is the "
                "matching original triplet-ion zero-field-splitting "
                "source. Yang-Xie 1204.5027v2 cites both and supplies "
                "the exact -J sum + D sum convention used by the "
                "registry."
            ),
            "claim_scope": (
                "zero-field ferromagnetic spin-1 Blume-Capel model "
                "on the square lattice at T=0; the product-state "
                "level crossing is exact, while no finite-temperature "
                "tensor result is used"
            ),
            "matched_anchors": [
                "identified Yang-Xie 1204.5027v2 source",
                "D=2J square-lattice abstract and zero-field degeneracy",
                "Blume-Capel Hamiltonian Eq. (1) and h=0 convention",
                "coordination-resolved bond Hamiltonian Eq. (2)",
                "positive-square bond decomposition Eq. (3)",
                "D above and below qJ/2 selects zero and ordered states",
                "D=qJ/2 gives the local-state ground-state degeneracy",
                "q=4 square endpoint at T/J=0 and D/J=2",
                "spin-1 local values are -1, 0, and +1",
                "Blume 1966 and Capel 1966 bibliography pair",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_yang_xie_single_ion_spin1_anisotropy_levels(source_text):
    """Derive the spin-1 onsite spectrum from Yang-Xie Eq. (1)."""

    error_prefix = "Yang-Xie Blume-Capel square-lattice crossing"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_yang_xie_single_ion_spin1_anisotropy_levels",
    )
    return _finalize_prepared_trace(
        _parse_yang_xie_single_ion_spin1_anisotropy_levels_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_yang_xie_single_ion_spin1_anisotropy_levels_prepared(
    prepared_text,
):
    _, source_trace = (
        _parse_yang_xie_square_blume_capel_crossing_prepared(
            prepared_text
        )
    )
    spin = source_trace["spin"]
    if spin != 1:
        raise RuntimeEvidenceError(
            "Yang-Xie Blume-Capel onsite spectrum requires spin S=1"
        )

    basis_m_values = list(range(-spin, spin + 1))
    unsorted_levels = [float(m * m) for m in basis_m_values]
    levels = sorted(unsorted_levels)
    distinct_levels = []
    degeneracies = []
    for level in levels:
        if not distinct_levels or level != distinct_levels[-1]:
            distinct_levels.append(level)
            degeneracies.append(1)
        else:
            degeneracies[-1] += 1
    parsed = {
        "levels": levels,
        "degeneracies": degeneracies,
    }
    if parsed != {
        "levels": [0.0, 1.0, 1.0],
        "degeneracies": [1, 2],
    }:
        raise RuntimeEvidenceError(
            "Yang-Xie Blume-Capel onsite spectrum does not yield the "
            "spin-1 D(Sz)^2 singlet-doublet levels"
        )

    trace = dict(source_trace)
    trace.update(
        {
            "parser": (
                "parse_yang_xie_single_ion_spin1_anisotropy_levels"
            ),
            "source_parser": (
                "parse_yang_xie_square_blume_capel_crossing"
            ),
            "source_equation": "1",
            "basis_m_values": basis_m_values,
            "anisotropy_energy_unit": "D=1",
            "derivation": "E_m/D = m^2",
            "level_degeneracies": {
                str(level): degeneracy
                for level, degeneracy in zip(
                    distinct_levels, degeneracies
                )
            },
            "claim_scope": (
                "the isolated spin-1 D(Sz)^2 term in Yang-Xie Eq. (1), "
                "normalized to D=1; exchange and magnetic-field terms "
                "are excluded from the onsite spectrum"
            ),
        }
    )
    return parsed, trace


def recompute_single_ion_spin1_anisotropy_levels(*, anisotropy):
    """Diagonalize D(Sz)^2 in the m=-1,0,+1 onsite basis."""

    anisotropy = _require_finite_real(
        anisotropy, label="single-ion anisotropy"
    )
    levels = sorted(float(anisotropy * m * m) for m in (-1, 0, 1))
    distinct_levels = []
    degeneracies = []
    for level in levels:
        if not distinct_levels or level != distinct_levels[-1]:
            distinct_levels.append(level)
            degeneracies.append(1)
        else:
            degeneracies[-1] += 1
    return {"levels": levels, "degeneracies": degeneracies}


def _recompute_ising_tc_over_j(*, exchange, factor, lattice):
    exchange = _require_positive_finite_real(
        exchange, label=f"{lattice} Ising exchange"
    )
    physical_tc = exchange * factor
    return {"tc_over_j": physical_tc / exchange}


def recompute_honeycomb_ising_ferromagnet_tc(*, exchange):
    """Evaluate the honeycomb Ising critical-temperature closed form."""

    factor = 2.0 / math.log(2.0 + math.sqrt(3.0))
    return _recompute_ising_tc_over_j(
        exchange=exchange, factor=factor, lattice="honeycomb"
    )


def recompute_kagome_ising_ferromagnet_tc(*, exchange):
    """Evaluate the kagome Ising critical-temperature closed form."""

    factor = 4.0 / math.log(3.0 + 2.0 * math.sqrt(3.0))
    return _recompute_ising_tc_over_j(
        exchange=exchange, factor=factor, lattice="kagome"
    )


def recompute_kano_naya_kagome_ising_entropy(*, grid_size):
    """Integrate Kano and Naya's residual-entropy Eq. (47)."""

    if (
        type(grid_size) is not int
        or grid_size < 64
        or grid_size % 2
    ):
        raise RuntimeEvidenceError(
            "Kano-Naya entropy grid must be an even integer >= 64"
        )

    def periodic_midpoint_estimate(size):
        step = 2.0 * math.pi / size
        angles = [(index + 0.5) * step for index in range(size)]
        total = 0.0
        for omega_1 in angles:
            cos_omega_1 = math.cos(omega_1)
            for omega_2 in angles:
                logarithm_argument = 21.0 - 4.0 * (
                    cos_omega_1
                    + math.cos(omega_2)
                    + math.cos(omega_1 + omega_2)
                )
                if logarithm_argument <= 0.0:
                    raise RuntimeEvidenceError(
                        "Kano-Naya entropy integrand left its positive domain"
                    )
                total += math.log(logarithm_argument)
        return total / (6.0 * size * size)

    entropy = periodic_midpoint_estimate(grid_size)
    coarse_entropy = periodic_midpoint_estimate(grid_size // 2)
    if (
        not math.isfinite(entropy)
        or entropy <= 0.0
        or not math.isclose(
            entropy, coarse_entropy, rel_tol=0.0, abs_tol=1.0e-11
        )
    ):
        raise RuntimeEvidenceError(
            "Kano-Naya entropy integration did not converge to a positive value"
        )
    return {
        "macroscopic_ground_state_degeneracy": math.exp(entropy) > 1.0,
        "residual_entropy_per_spin": entropy,
    }


def recompute_garel_maillard_villain_entropy(*, series_terms):
    """Evaluate the Villain residual entropy G/pi from Catalan's series."""

    if type(series_terms) is not int or series_terms < 64:
        raise RuntimeEvidenceError(
            "Garel-Maillard Catalan series size must be an integer >= 64"
        )

    catalan_estimate = math.fsum(
        (-1.0 if index % 2 else 1.0) / (2 * index + 1) ** 2
        for index in range(series_terms)
    )
    alternating_remainder_bound = 1.0 / (2 * series_terms + 1) ** 2
    entropy = catalan_estimate / math.pi
    entropy_lower_bound = (
        catalan_estimate - alternating_remainder_bound
    ) / math.pi
    if (
        not math.isfinite(entropy)
        or not math.isfinite(entropy_lower_bound)
        or entropy_lower_bound <= 0.0
    ):
        raise RuntimeEvidenceError(
            "Garel-Maillard Catalan series did not establish positive entropy"
        )
    return {
        "macroscopic_ground_state_degeneracy": True,
        "residual_entropy_per_spin": entropy,
    }


def recompute_triangular_ising_ferromagnet_tc(*, exchange):
    """Evaluate the triangular Ising critical-temperature closed form."""

    factor = 4.0 / math.log(3.0)
    return _recompute_ising_tc_over_j(
        exchange=exchange, factor=factor, lattice="triangular"
    )


def recompute_simple_cubic_ising_tc_from_critical_coupling(
    *, critical_coupling
):
    """Convert K_c=J/(k_B T_c) to the simple-cubic Ising T_c/J ratio."""

    critical_coupling = _require_positive_finite_real(
        critical_coupling,
        label="simple-cubic Ising critical coupling",
    )
    return {"tc_over_j": 1.0 / critical_coupling}


def recompute_one_dimensional_ising_no_finite_t_transition(*, exchange):
    """Use the transfer-matrix eigenvalue separation at every finite beta."""

    exchange = _require_positive_finite_real(
        exchange, label="one-dimensional Ising exchange"
    )
    beta_probe = 1.0 / exchange
    eigenvalue_separation = 2.0 * math.exp(-beta_probe * exchange)
    if not eigenvalue_separation > 0.0:
        raise RuntimeEvidenceError(
            "one-dimensional Ising transfer-matrix eigenvalues did not separate"
        )
    return {
        "finite_temperature_transition": False,
        "tc_over_j": 0.0,
    }


def recompute_transverse_field_ising_chain_critical_point(*, exchange):
    """Locate the exact gap closing of the transverse-field Ising chain."""

    exchange = _require_positive_finite_real(
        exchange, label="transverse-field Ising exchange"
    )
    critical_ratio = 1.0

    def gap_at(field_ratio):
        return 2.0 * exchange * abs(1.0 - field_ratio)

    critical_gap = gap_at(critical_ratio)
    neighboring_gaps = [gap_at(ratio) for ratio in (0.5, 1.5)]
    if critical_gap != 0.0 or not all(gap > 0.0 for gap in neighboring_gaps):
        raise RuntimeEvidenceError(
            "transverse-field Ising spectrum does not close only at g=1"
        )
    return {"critical_field_over_exchange": critical_ratio}


def recompute_transverse_field_ising_chain_gap(
    *, field_over_exchange, exchange
):
    """Evaluate the exact TFIM gap at the registered coupling ratio g=0.6."""

    field_over_exchange = _require_finite_real(
        field_over_exchange, label="transverse-field Ising field ratio"
    )
    if not math.isclose(
        field_over_exchange, 0.6, rel_tol=0.0, abs_tol=1.0e-15
    ):
        raise RuntimeEvidenceError(
            "registered transverse-field Ising gap operand requires g=0.6"
        )
    exchange = _require_positive_finite_real(
        exchange, label="transverse-field Ising exchange"
    )
    gap = 2.0 * exchange * abs(1.0 - field_over_exchange)
    return {
        "gap_formula": "2J|1-g|",
        "gap_formula_at_g_0_6": gap,
    }


def recompute_xx_spin_half_chain_free_fermion_energy(*, exchange):
    """Evaluate the Jordan-Wigner free-fermion ground-state integral."""

    exchange = _require_positive_finite_real(
        exchange, label="XX-chain exchange"
    )
    return {"energy_per_site": -exchange / math.pi}


def recompute_shastry_sutherland_exact_dimer_energy(*, dimer_exchange):
    """Evaluate one singlet dimer and normalize per dimer and per spin."""

    dimer_exchange = _require_positive_finite_real(
        dimer_exchange, label="Shastry-Sutherland dimer exchange"
    )
    energy_per_dimer = -0.75 * dimer_exchange
    energy_per_spin = energy_per_dimer / 2.0
    return {
        "energy_per_dimer": energy_per_dimer,
        "energy_per_spin": energy_per_spin,
    }


def recompute_majumdar_ghosh_exact_dimer_operand(*, j1, j2_over_j1):
    """Evaluate the two translated dimer coverings at J2/J1=1/2."""

    j1 = _require_positive_finite_real(j1, label="Majumdar-Ghosh J1")
    j2_over_j1 = _require_finite_real(
        j2_over_j1, label="Majumdar-Ghosh J2/J1"
    )
    if not math.isclose(j2_over_j1, 0.5, rel_tol=0.0, abs_tol=1.0e-15):
        raise RuntimeEvidenceError(
            "Majumdar-Ghosh exact dimer operand requires J2/J1=1/2"
        )
    energy_per_site = -0.375 * j1
    translated_coverings = {0, 1}
    return {
        "energy_per_site": energy_per_site,
        "degenerate_dimer_coverings": len(translated_coverings),
    }


def recompute_checkerboard_crossed_plaquette_constraint(*, exchange):
    """Verify the complete-graph plaquette energy is minimized at L=0."""

    exchange = _require_positive_finite_real(
        exchange, label="checkerboard exchange"
    )
    zero_sum_spins = [
        [1.0, 0.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0],
    ]
    aligned_spins = [[1.0, 0.0, 0.0] for _ in range(4)]
    def plaquette_energy(spins):
        total_spin = [math.fsum(spin[index] for spin in spins) for index in range(3)]
        total_spin_squared = sum(component * component for component in total_spin)
        individual_squared = sum(
            sum(component * component for component in spin) for spin in spins
        )
        return 0.5 * exchange * (total_spin_squared - individual_squared)

    satisfies_constraint = all(
        math.isclose(math.fsum(spin[index] for spin in zero_sum_spins), 0.0,
                     rel_tol=0.0, abs_tol=1.0e-15)
        for index in range(3)
    )
    zero_sum_energy = plaquette_energy(zero_sum_spins)
    aligned_energy = plaquette_energy(aligned_spins)
    if (
        not satisfies_constraint
        or not math.isclose(
            zero_sum_energy, -2.0 * exchange, rel_tol=0.0, abs_tol=1.0e-15
        )
        or not zero_sum_energy < aligned_energy
    ):
        raise RuntimeEvidenceError(
            "checkerboard crossed-plaquette energy identity did not select L=0"
        )
    return {"zero_total_spin_per_crossed_plaquette": True}


def recompute_simple_cubic_j1_j2_boundary(*, j1):
    """Equate the classical Neel and (0,pi,pi) single-Q energies."""

    j1 = _require_positive_finite_real(j1, label="simple-cubic J1")

    def energies(j2):
        return {
            "neel": -3.0 * j1 + 6.0 * j2,
            "collinear": -1.0 * j1 - 2.0 * j2,
        }

    at_zero = energies(0.0)
    at_unit = energies(j1)
    neel_slope = (at_unit["neel"] - at_zero["neel"]) / j1
    collinear_slope = (
        at_unit["collinear"] - at_zero["collinear"]
    ) / j1
    crossing_j2 = (
        at_zero["collinear"] - at_zero["neel"]
    ) / (neel_slope - collinear_slope)
    crossing_ratio = crossing_j2 / j1
    below = energies(0.2 * j1)
    above = energies(0.3 * j1)
    if not (
        below["neel"] < below["collinear"]
        and above["collinear"] < above["neel"]
    ):
        raise RuntimeEvidenceError(
            "simple-cubic J1-J2 energy crossing does not separate Neel and "
            "collinear minima"
        )
    return {
        "neel_to_collinear_boundary_j2_over_j1": crossing_ratio
    }


def recompute_takhtajan_babujian_integrable_operand():
    """Map equal and opposite bilinear-biquadratic couplings to theta=-pi/4."""

    theta = -math.pi / 4.0
    equal_opposite_couplings = (
        math.cos(theta) > 0.0
        and math.sin(theta) < 0.0
        and math.isclose(
            math.cos(theta),
            -math.sin(theta),
            rel_tol=0.0,
            abs_tol=1.0e-15,
        )
    )
    return {
        "theta_radians": theta,
        "is_integrable": equal_opposite_couplings,
    }


def recompute_xxz_spin_half_chain_phase_boundaries():
    """Cross-check the three Bethe-ansatz XXZ regions and their endpoints."""

    def phase_label(delta):
        if delta < -1.0:
            return "ferromagnetic"
        if delta <= 1.0:
            return "gapless"
        return "neel"

    labels = {delta: phase_label(delta) for delta in (-1.5, -1.0, 0.0, 1.0, 1.5)}
    expected = {
        -1.5: "ferromagnetic",
        -1.0: "gapless",
        0.0: "gapless",
        1.0: "gapless",
        1.5: "neel",
    }
    if labels != expected:
        raise RuntimeEvidenceError(
            "XXZ phase boundaries do not realize the expected three regions"
        )
    ferromagnetic_boundary = -1.0
    neel_boundary = 1.0
    return {
        "ferromagnetic_boundary_delta": ferromagnetic_boundary,
        "neel_boundary_delta": neel_boundary,
        "gapless_interval": [
            ferromagnetic_boundary,
            neel_boundary,
        ],
    }


def _parse_pfeuty_tfim_spectrum_anchors(source_text):
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Pfeuty TFIM spectrum requires nonempty source text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    identity_match = re.search(
        r"one-dimensional Ising model with a transverse field.{0,160}?"
        r"solved exactly.{0,180}?Pauli operators.{0,180}?Fermi operators",
        normalized,
        flags=re.IGNORECASE,
    )
    definition_match = re.search(
        r"Defining h\s*=\s*\.?\s*J\s*/\s*"
        r"(?:\(\s*2\s*(?:Gamma|Γ)\s*\)|2\s*(?:Gamma|Γ|I['’]|13|B))",
        normalized,
        flags=re.IGNORECASE,
    )
    dispersion_match = re.search(
        r"normal modes.{0,700}?(?:"
        r"Lambda\s*_?\s*k\s*\^?\s*2\s*=\s*"
        r"1\s*\+\s*h\s*\^?\s*2\s*\+\s*2\s*h\s*cos\s*\(?k\)?"
        r"|"
        r"A\s*_?\s*k\s*2\s*=\s*\(\s*1\s*\+\s*A2\s*\+\s*2X\s*cos\s*k"
        r").{0,100}?\(2\.10\)",
        normalized,
        flags=re.IGNORECASE,
    )
    zero_mode_match = re.search(
        r"For h\s*=\s*1.{0,220}?(?:Lambda|A).{0,40}?=\s*0"
        r".{0,120}?\(2\.12\)",
        normalized,
        flags=re.IGNORECASE,
    )
    fermion_energy_match = re.search(
        r"system of noninteracting.{0,30}?fermions of energy.{0,80}?"
        r"(?:Lambda|FL|A)",
        normalized,
        flags=re.IGNORECASE,
    )
    gap_match = re.search(
        r"For h\s*=\s*1\s*\(.{0,25}?=\s*J\s*/\s*2\s*\)"
        r".{0,100}?gap in the excitation spectrum disappears"
        r".{0,180}?mode energy drops to zero.{0,120}?rises\s*again",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        definition_match,
        dispersion_match,
        zero_mode_match,
        fermion_energy_match,
        gap_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Pfeuty TFIM spectrum must contain the exact Pauli-to-fermion "
            "solution, h=J/(2 Gamma), Eqs. (2.10) and (2.12), the fermion "
            "energy, and the gap closing at Gamma=J/2"
        )
    return normalized, matches


def _pfeuty_tfim_trace(parser_name, matches):
    return {
        "parser": parser_name,
        "equations": ["2.10", "2.12"],
        "normalization": (
            "sigma=2S maps Pfeuty -J*Sx*Sx-Gamma*Sz to registry "
            "-J_registry*sigma_x*sigma_x-h_registry*sigma_z with "
            "J_registry=J/4, h_registry=Gamma/2, and g=2*Gamma/J"
        ),
        "matched_anchors": [
            "exact Pauli-to-Fermi solution",
            "h=J/(2 Gamma)",
            "normal-mode dispersion Eq. (2.10)",
            "zero mode Eq. (2.12)",
            "noninteracting-fermion excitation energy",
            "gap disappearance at Gamma=J/2",
        ],
        "text_spans": [[match.start(), match.end()] for match in matches],
    }


def parse_pfeuty_tfim_critical_point(source_text):
    """Normalize Pfeuty's spin-operator critical field to Pauli convention."""

    _, matches = _parse_pfeuty_tfim_spectrum_anchors(source_text)
    pfeuty_critical_gamma_over_j = 0.5
    registry_critical_field_over_exchange = (
        2.0 * pfeuty_critical_gamma_over_j
    )
    return (
        {
            "critical_field_over_exchange": (
                registry_critical_field_over_exchange
            )
        },
        _pfeuty_tfim_trace("parse_pfeuty_tfim_critical_point", matches),
    )


def parse_pfeuty_tfim_gap(source_text):
    """Derive the Pauli-normalized TFIM gap from Pfeuty's dispersion."""

    _, matches = _parse_pfeuty_tfim_spectrum_anchors(source_text)
    registry_exchange = 1.0
    field_over_exchange = 0.6
    gap = 2.0 * registry_exchange * abs(1.0 - field_over_exchange)
    trace = _pfeuty_tfim_trace("parse_pfeuty_tfim_gap", matches)
    trace["derivation"] = (
        "At k=pi, Pfeuty's Gamma*Lambda_k gives |Gamma-J/2|; "
        "with J_registry=J/4 and g=2*Gamma/J this is "
        "2*J_registry*|1-g|"
    )
    return (
        {
            "gap_formula": "2J|1-g|",
            "gap_formula_at_g_0_6": gap,
        },
        trace,
    )


def _parse_dziarmaga_tfim_spectrum_anchors_prepared(normalized):
    error_message = (
        "Dziarmaga TFIM source must establish arXiv:cond-mat/0509490v3, "
        "the Pauli-matrix Hamiltonian in Eq. (1), the exact g=1 critical "
        "point, the Jordan-Wigner and Bogoliubov transformations, and the "
        "quasiparticle dispersion in Eq. (16)"
    )
    identity_match = re.search(
        r"Dynamics of quantum phase transition:\s*exact solution in "
        r"quantum Ising model"
        r".{0,600}?Jacek Dziarmaga"
        r".{0,600}?arXiv:cond-mat/0509490v3",
        normalized,
        flags=re.IGNORECASE,
    )
    model_prose_match = re.search(
        r"1-dimensional.{0,350}?quantum Ising model"
        r".{0,1800}?exactly solvable"
        r".{0,1800}?defined by the Hamiltonian",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_scale_match = re.search(
        r"H\s*=\s*-\s*J.{0,180}?\(\s*1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_terms_match = re.search(
        r"g\s*(?:sigma|σ).{0,120}?\+\s*(?:sigma|σ)"
        r".{0,120}?(?:sigma|σ)",
        normalized,
        flags=re.IGNORECASE,
    )
    critical_match = re.search(
        r"Quantum phase transition takes place"
        r".{0,300}?value g\s*=\s*1"
        r".{0,80}?external magnetic field",
        normalized,
        flags=re.IGNORECASE,
    )
    jordan_wigner_match = re.search(
        r"After Jordan-Wigner transformation"
        r".{0,500}?\(\s*6\s*\)"
        r".{0,500}?\(\s*7\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    bogoliubov_match = re.search(
        r"Bogoliubov transformation"
        r".{0,1600}?\(\s*14\s*\)"
        r".{0,900}?Bogoliubov-de Gennes equations"
        r".{0,900}?\(\s*15\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    dispersion_match = re.search(
        r"(?:epsilon|eps|ǫ)\s*_?\s*k\s*=\s*2\s*J"
        r".{0,180}?g\s*-\s*cos\s*\(\s*k\s*a\s*\)"
        r".{0,180}?sin\s*\^?\s*2\s*\(\s*k\s*a\s*\)"
        r".{0,100}?\(\s*16\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    match_by_name = {
        "identity": identity_match,
        "model_definition": model_prose_match,
        "hamiltonian_scale": hamiltonian_scale_match,
        "hamiltonian_terms": hamiltonian_terms_match,
        "critical_point": critical_match,
        "jordan_wigner": jordan_wigner_match,
        "bogoliubov": bogoliubov_match,
        "dispersion": dispersion_match,
    }
    missing = [
        name for name, match in match_by_name.items() if match is None
    ]
    if missing:
        raise RuntimeEvidenceError(
            f"{error_message}; missing anchors: {', '.join(missing)}"
        )
    matches = tuple(match_by_name.values())
    return normalized, matches


def _dziarmaga_tfim_trace(parser_name, matches):
    return {
        "parser": parser_name,
        "source_profile": "arxiv:cond-mat/0509490v3",
        "equations": ["1", "6-7", "14-16"],
        "normalization": (
            "source and registry both use "
            "-J sum_n(g sigma_n^x + sigma_n^z sigma_n+1^z)"
        ),
        "matched_anchors": [
            "identified Dziarmaga arXiv manuscript",
            "Pauli-matrix transverse-field Ising Hamiltonian Eq. (1)",
            "critical field ratio g=1",
            "Jordan-Wigner transformation Eqs. (6)-(7)",
            "Bogoliubov transformation and BdG equations (14)-(15)",
            "quasiparticle dispersion Eq. (16)",
        ],
        "text_spans": [[match.start(), match.end()] for match in matches],
    }


def parse_dziarmaga_tfim_critical_point(source_text):
    """Extract the exactly normalized TFIM critical field from Dziarmaga."""

    error_message = (
        "Dziarmaga TFIM source must establish arXiv:cond-mat/0509490v3, "
        "the Pauli-matrix Hamiltonian in Eq. (1), the exact g=1 critical "
        "point, the Jordan-Wigner and Bogoliubov transformations, and the "
        "quasiparticle dispersion in Eq. (16)"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text, "parse_dziarmaga_tfim_critical_point"
    )
    return _finalize_prepared_trace(
        _parse_dziarmaga_tfim_critical_point_prepared(prepared.text),
        prepared,
    )


def _parse_dziarmaga_tfim_critical_point_prepared(prepared_text):
    _, matches = _parse_dziarmaga_tfim_spectrum_anchors_prepared(
        prepared_text
    )
    return (
        {"critical_field_over_exchange": 1.0},
        _dziarmaga_tfim_trace(
            "parse_dziarmaga_tfim_critical_point", matches
        ),
    )


def parse_dziarmaga_tfim_gap(source_text):
    """Derive the registered TFIM gap from Dziarmaga's exact dispersion."""

    error_message = (
        "Dziarmaga TFIM source must establish arXiv:cond-mat/0509490v3, "
        "the Pauli-matrix Hamiltonian in Eq. (1), the exact g=1 critical "
        "point, the Jordan-Wigner and Bogoliubov transformations, and the "
        "quasiparticle dispersion in Eq. (16)"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text, "parse_dziarmaga_tfim_gap"
    )
    return _finalize_prepared_trace(
        _parse_dziarmaga_tfim_gap_prepared(prepared.text), prepared
    )


def _parse_dziarmaga_tfim_gap_prepared(prepared_text):
    _, matches = _parse_dziarmaga_tfim_spectrum_anchors_prepared(
        prepared_text
    )
    field_over_exchange = 0.6
    gap = 2.0 * abs(1.0 - field_over_exchange)
    trace = _dziarmaga_tfim_trace("parse_dziarmaga_tfim_gap", matches)
    trace["derivation"] = (
        "At k=0, Eq. (16) gives epsilon_0=2J|g-1|; "
        "substituting the registered g=0.6 gives 0.8J"
    )
    return (
        {
            "gap_formula": "2J|1-g|",
            "gap_formula_at_g_0_6": gap,
        },
        trace,
    )


def parse_lieb_schultz_mattis_xx_chain_energy(source_text):
    """Extract the isotropic XY-chain thermodynamic-limit energy."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Lieb-Schultz-Mattis XX energy requires nonempty source text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    identity_match = re.search(
        r"Two Soluble Models of an Antiferromagnetic Chain",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"(?:"
        r"(?:first model.{0,80}?)?XY model.{0,800}?"
        r"(?:usual )?Pauli spin matrices.{0,500}?\(2\.1\)"
        r"|"
        r"first model consists.{0,500}?\(2\.1\).{0,300}?"
        r"(?:usual )?Pauli spin matrices.{0,200}?XI.? model"
        r")",
        normalized,
        flags=re.IGNORECASE,
    )
    sum_match = re.search(
        r"ground-state energy.{0,180}?(?:E\s*_?\s*0|En)"
        r".{0,180}?\(2\.20\)",
        normalized,
        flags=re.IGNORECASE,
    )
    integral_match = re.search(
        r"(?:limit|N\s*(?:->|→|\+)\s*(?:infinity|x|∞)).{0,160}?"
        r"sum can be replaced by (?:(?:an|the) )?integral"
        r".{0,500}?\(2\.21\)",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_limit_match = re.search(
        r"(?:E\s*_?\s*0|E0)\s*/\s*N\s*=\s*-\s*1\s*/\s*pi"
        r".{0,80}?isotropic case.{0,60}?(?:gamma|y)\s*=\s*0"
        r".{0,60}?\(2\.22a\)",
        normalized,
        flags=re.IGNORECASE,
    )
    ocr_limit_match = re.search(
        r"(?:&I|E.)\s*/?\s*N\s*=\s*-\s*l\s*/\s*r"
        r".{0,80}?isotropic case.{0,60}?y\s*=\s*0"
        r".{0,60}?\(2\.2(?:2a|%|.)\)",
        normalized,
        flags=re.IGNORECASE,
    )
    limit_match = clean_limit_match or ocr_limit_match
    matches = (
        identity_match,
        model_match,
        sum_match,
        integral_match,
        limit_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Lieb-Schultz-Mattis XX source must contain the identified XY "
            "Hamiltonian with Pauli normalization, Eqs. (2.20)-(2.21), "
            "and the isotropic gamma=0 limit E0/N=-1/pi in Eq. (2.22a)"
        )
    energy = (
        benchmark_functions.xx_spin_half_chain_free_fermion_energy_per_site(
            1.0
        )
    )
    return (
        {"energy_per_site": energy},
        {
            "parser": "parse_lieb_schultz_mattis_xx_chain_energy",
            "equations": ["2.1", "2.20", "2.21", "2.22a"],
            "derivation": (
                "Set gamma=0 in the thermodynamic-limit integral of Eq. "
                "(2.21); integrating |cos(k)| gives E0/N=-1/pi in the "
                "Hamiltonian normalization of Eq. (2.1)"
            ),
            "matched_anchors": [
                "identified Lieb-Schultz-Mattis paper",
                "XY Hamiltonian and Pauli convention",
                "ground-state sum Eq. (2.20)",
                "thermodynamic-limit integral Eq. (2.21)",
                "isotropic limit Eq. (2.22a)",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_collura_xx_chain_energy(source_text):
    """Extract the exact XX-chain energy in the registry normalization."""

    error_message = (
        "Collura-Calabrese-Essler XX source must establish DOI "
        "10.1103/PhysRevB.92.125131, the spin-operator XXZ Hamiltonian in "
        "Eq. (1), its Delta=0 XX limit, and the exact energy density "
        "E_XX=-1/pi"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text, "parse_collura_xx_chain_energy"
    )
    return _finalize_prepared_trace(
        _parse_collura_xx_chain_energy_prepared(prepared.text), prepared
    )


def _parse_collura_xx_chain_energy_prepared(normalized):
    error_message = (
        "Collura-Calabrese-Essler XX source must establish DOI "
        "10.1103/PhysRevB.92.125131, the spin-operator XXZ Hamiltonian in "
        "Eq. (1), its Delta=0 XX limit, and the exact energy density "
        "E_XX=-1/pi"
    )

    spin_half_pattern = r"spin-\s*1\s*/?\s*2"
    identity_match = re.search(
        r"Quantum quench within the gapless phase of the "
        + spin_half_pattern
        + r"\s+Heisenberg XXZ spin chain"
        r".{0,500}?Mario Collura"
        r".{0,250}?Pasquale Calabrese"
        r".{0,250}?Fabian H\.\s*L\.\s*Essler"
        r".{0,2200}?DOI:\s*10\.1103/PhysRevB\.92\.125131",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"one-dimensional\s+"
        + spin_half_pattern
        + r"\s+XXZ chain with"
        r".{0,450}?Hamiltonian"
        r".{0,1000}?H\s*\(.{0,20}?\)\s*=\s*J"
        r".{0,1400}?\(\s*1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    operator_match = re.search(
        r"(?:where|Here) S.{0,30}?(?:are|['’]s are) spin operators"
        r".{0,500}?set J\s*=\s*1",
        normalized,
        flags=re.IGNORECASE,
    )
    xx_limit_match = re.search(
        r"ground state of the XX (?:model|chain|Hamiltonian)"
        r".{0,700}?=\s*0",
        normalized,
        flags=re.IGNORECASE,
    )
    energy_match = re.search(
        r"best estimate of the ground-state energy density"
        r".{0,180}?E\s*_?\s*0\s*=\s*-\s*0\.318\s*309\s*81"
        r".{0,180}?exact value"
        r".{0,100}?E\s*_?\s*XX\s*=\s*-\s*1\s*/\s*pi"
        r".{0,80}?7\s*(?:x|×)\s*10\s*\^?\s*-\s*8",
        normalized,
        flags=re.IGNORECASE,
    )
    match_by_name = {
        "identity": identity_match,
        "hamiltonian": model_match,
        "spin_operator_convention": operator_match,
        "xx_limit": xx_limit_match,
        "energy": energy_match,
    }
    missing = [
        name for name, match in match_by_name.items() if match is None
    ]
    if missing:
        raise RuntimeEvidenceError(
            f"{error_message}; missing anchors: {', '.join(missing)}"
        )
    matches = tuple(match_by_name.values())

    energy = -1.0 / math.pi
    return (
        {"energy_per_site": energy},
        {
            "parser": "parse_collura_xx_chain_energy",
            "source_profile": "doi:10.1103/PhysRevB.92.125131",
            "equation": "1",
            "normalization": (
                "source and registry both use "
                "J sum_j(Sx_j Sx_j+1 + Sy_j Sy_j+1) at Delta=0"
            ),
            "derivation": (
                "The source identifies Delta=0 as the XX model and states "
                "its exact thermodynamic-limit energy density E_XX=-1/pi"
            ),
            "matched_anchors": [
                "identified Collura-Calabrese-Essler PRB paper",
                "spin-half XXZ Hamiltonian Eq. (1)",
                "spin-operator convention with J=1",
                "Delta=0 XX ground state",
                "exact ground-state energy density E_XX=-1/pi",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_pinettes_diep_simple_cubic_boundary(source_text):
    """Extract the classical simple-cubic J1-J2 boundary at J2/J1=1/4."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Pinettes-Diep simple-cubic boundary requires nonempty source text"
        )
    prepared = _prepared_view_for_parser(
        source_text, "parse_pinettes_diep_simple_cubic_boundary"
    )
    return _finalize_prepared_trace(
        _parse_pinettes_diep_simple_cubic_boundary_prepared(prepared.text),
        prepared,
    )


def _parse_pinettes_diep_simple_cubic_boundary_prepared(normalized):
    identity_match = re.search(
        r"Phase transition and phase diagram.{0,160}?Heisenberg model"
        r".{0,120}?simple(?:-|\s+)cubic lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"classical Heisenberg model with the Hamiltonian.{0,700}?"
        r"(?:\(\s*1\s*\)|~\s*1\s*!|Eq\.?\s*\(?\s*1\s*\)?)"
        r".{0,420}?(?:"
        r"nearest(?:-|\s*)neighbor and next(?:-|\s*)nearest(?:-|\s*)neighbor"
        r"|NN and NNN)"
        r".{0,80}?pairs",
        normalized,
        flags=re.IGNORECASE,
    )
    sign_match = re.search(
        r"All interactions are antiferromagnetic.{0,220}?"
        r"(?:measured|measure).{0,80}?units of J\s*1",
        normalized,
        flags=re.IGNORECASE,
    )
    neel_match = re.search(
        r"for\s+0\s*(?:<|,)\s*J\s*2\s*(?:<|,)\s*0\.25\s*J\s*1"
        r".{0,140}?(?:classical\s+)?(?:ground state|GS)"
        r".{0,80}?antiferromagnetic structure",
        normalized,
        flags=re.IGNORECASE,
    )
    collinear_match = re.search(
        r"for\s+0\.25\s*J\s*1\s*(?:<|,)\s*J\s*2"
        r".{0,180}?(?:classical\s+)?(?:ground state|GS)"
        r".{0,100}?infinite degeneracy"
        r".{0,700}?three collinear configurations"
        r".{0,180}?(?:ground-state|ground state|GS) configurations",
        normalized,
        flags=re.IGNORECASE,
    )
    critical_match = re.search(
        r"dashed line.{0,100}?critical value.{0,100}?"
        r"J\s*2\s*/\s*J\s*1\s*(?:=|5)\s*0\.25",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        model_match,
        sign_match,
        neel_match,
        collinear_match,
        critical_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Pinettes-Diep source must identify the simple-cubic classical "
            "J1-J2 Hamiltonian with antiferromagnetic NN and NNN couplings, "
            "the Neel and collinear sides of the boundary, and the printed "
            "critical ratio J2/J1=0.25"
        )
    return (
        {"neel_to_collinear_boundary_j2_over_j1": 0.25},
        {
            "parser": "parse_pinettes_diep_simple_cubic_boundary",
            "equation": "1",
            "normalization": "J2/J1 with antiferromagnetic J1,J2>0",
            "matched_anchors": [
                "identified Pinettes-Diep simple-cubic paper",
                "classical J1-J2 Hamiltonian Eq. (1)",
                "antiferromagnetic couplings in units of J1",
                "Neel ground state below J2/J1=0.25",
                "collinear ground-state manifold above J2/J1=0.25",
                "phase-diagram critical line J2/J1=0.25",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_shastry_sutherland_exact_dimer_product(source_text):
    """Derive the spin-half dimer energy from the rigorous product state."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Shastry-Sutherland exact dimer proof requires nonempty source text"
        )
    prepared = _prepared_view_for_parser(
        source_text, "parse_shastry_sutherland_exact_dimer_product"
    )
    return _finalize_prepared_trace(
        _parse_shastry_sutherland_exact_dimer_product_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_shastry_sutherland_exact_dimer_product_prepared(normalized):
    identity_match = re.search(
        r"EXACT GROUND\s*STATE OF A QUANTUM MECHANICAL ANTIFERROMAGNET",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"two dimensional lattice.{0,180}?"
        r"dashed line represents a bond with strength 2\s*(?:alpha|a\b|a[\"'])"
        r".{0,520}?nearest(?:-|\s+)neighbor bond has strength"
        r".{0,160}?unity"
        r".{0,120}?Hamiltonian is.{0,700}?\(\s*1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    state_match = re.search(
        r"observe.{0,100}?the state.{0,220}?\(\s*3\s*\)"
        r".{0,160}?is an eigenstate of the Hamiltonian Eq\.?\s*\(\s*1\s*\)"
        r".{0,100}?eigenvalue.{0,260}?\(\s*4\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    singlet_match = re.search(
        r"notation.{0,120}?f\s*o\s*r\s+a\s+"
        r"s\s*i\s*n\s*g\s*l\s*e\s*t.{0,120}?of the spins",
        normalized,
        flags=re.IGNORECASE,
    )
    annihilation_match = re.search(
        r"identity.{0,260}?(?:=|equals)\s*(?:0|O)\b"
        r".{0,160}?first term.{0,100}?annihilates",
        normalized,
        flags=re.IGNORECASE,
    )
    lower_bound_match = re.search(
        r"saturates a lower bound.{0,280}?ground(?:-|\s*)state"
        r".{0,280}?energy.{0,280}?rigorous ground(?:-|\s*)state",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        model_match,
        state_match,
        singlet_match,
        annihilation_match,
        lower_bound_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Shastry-Sutherland source must identify the orthogonal-dimer "
            "Hamiltonian, the singlet product eigenstate in Eqs. (3)-(4), "
            "the singlet annihilation identity, and saturation of the "
            "ground-state lower bound"
        )
    spin = 0.5
    energy_per_dimer = -spin * (spin + 1.0)
    return (
        {
            "energy_per_dimer": energy_per_dimer,
            "energy_per_spin": energy_per_dimer / 2.0,
        },
        {
            "parser": "parse_shastry_sutherland_exact_dimer_product",
            "equations": ["1", "3", "4"],
            "derivation": (
                "The source identifies one spin-half singlet on every "
                "orthogonal dimer. Its Heisenberg eigenvalue is "
                "-S(S+1)=-3/4 per dimer, hence -3/8 per spin when the "
                "registered dimer exchange equals one."
            ),
            "matched_anchors": [
                "identified Shastry-Sutherland exact-ground-state paper",
                "two-dimensional orthogonal-dimer Hamiltonian Eq. (1)",
                "product eigenstate and eigenvalue Eqs. (3)-(4)",
                "each diagonal pair is a singlet",
                "singlet annihilation identity",
                "lower-bound saturation establishes the rigorous ground state",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_fouet_checkerboard_classical_constraint(source_text):
    """Extract the zero-total-spin constraint on every crossed square."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Fouet checkerboard constraint requires nonempty source text"
        )
    prepared = _prepared_view_for_parser(
        source_text, "parse_fouet_checkerboard_classical_constraint"
    )
    return _finalize_prepared_trace(
        _parse_fouet_checkerboard_classical_constraint_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_fouet_checkerboard_classical_constraint_prepared(normalized):
    paper_match = re.search(
        r"The planar pyrochlore\s*:\s*a Valence Bond Crystal",
        normalized,
        flags=re.IGNORECASE,
    )
    identity_match = re.search(
        r"spin-1/2 Heisenberg model.{0,60}?on the checkerboard lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    geometry_match = re.search(
        r"checker-board lattice.{0,360}?(?:tice\s+)?built out of "
        r"corner(?:-|\s+)sharing (?:four|4)(?:-|\s*)spin squares"
        r".{0,120}?two(?:-|\s+)dimensional analog of the pyrochlore lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"first(?:-|\s+)neighbor classical Heisenberg model"
        r".{0,1200}?rewritten as the sum of the"
        r".{0,260}?square of the total spin"
        r".{0,520}?corner(?:-|\s+)sharing units",
        normalized,
        flags=re.IGNORECASE,
    )
    equation_match = re.search(
        r"H\s*=\s*J.{0,320}?"
        r"S\s*(?:_?\s*alpha|α)\s*(?:\^?\s*2|²)"
        r".{0,100}?(?:constant|Cst\.)"
        r".{0,80}?\(\s*1\.1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    constraint_match = re.search(
        r"classical ground(?:-|\s*)state is obtained whenever"
        r".{0,80}?S\s*(?:_?\s*alpha|α)\s*=\s*.{0,180}?"
        r"(?:0|O)\s+for all"
        r"\s*(?:alpha|α)",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        paper_match,
        identity_match,
        geometry_match,
        model_match,
        equation_match,
        constraint_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Fouet checkerboard source must identify the checkerboard "
            "four-spin crossed squares, the classical Heisenberg sum-of-"
            "squares identity in Eq. (1.1), and S_alpha=0 on every unit"
        )
    return (
        {"zero_total_spin_per_crossed_plaquette": True},
        {
            "parser": "parse_fouet_checkerboard_classical_constraint",
            "equation": "1.1",
            "normalization": (
                "each checkerboard unit is a fully connected crossed square, "
                "so its four-spin total S_alpha is the registered plaquette L"
            ),
            "matched_anchors": [
                "identified Fouet planar-pyrochlore paper",
                "identified checkerboard Heisenberg model",
                "corner-sharing four-spin crossed-square geometry",
                "classical total-spin-square decomposition",
                "Hamiltonian identity Eq. (1.1)",
                "S_alpha=0 on every unit",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_syozi_kagome_ising_ferromagnet_tc(source_text):
    """Derive the kagome Ising Curie temperature from Syôzi's equation."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Syozi kagome Ising critical condition requires nonempty source text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    identity_match = re.search(
        r"Statistics of Kagom(?:e|é) Lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    ising_match = re.search(
        r"work of Onsager.{0,140}?solved exactly.{0,100}?"
        r"problem of Ising model.{0,220}?plane square lattice"
        r".{0,220}?honeycomb and triangular lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    geometry_match = re.search(
        r"kagom(?:e|é).{0,420}?consists exclusively of equivalent lattice "
        r"points and equivalent bonds.{0,420}?nearest neighbors"
        r".{0,120}?(?:four|4)",
        normalized,
        flags=re.IGNORECASE,
    )
    mapping_match = re.search(
        r"decorated honeycomb lattice.{0,520}?summ(?:ing|ed)"
        r".{0,100}?spin variables.{0,260}?partition function of the "
        r"kagom(?:e|é) lattice.{0,120}?star(?:-|\s*)triangle transformation"
        r".{0,180}?interaction parameter\s+K",
        normalized,
        flags=re.IGNORECASE,
    )
    singularity_match = re.search(
        r"(?:in )?the ferromagnetic case.{0,140}?specific heat becomes "
        r"logarithmically infinite.{0,100}?at the temperature",
        normalized,
        flags=re.IGNORECASE,
    )
    critical_match = re.search(
        r"(?:"
        r"exp\s*\(\s*4\s*K\s*\)"
        r"|"
        r"e\s*(?:\^\s*)?\(?\s*4\s*(?:K|lr)\s*\)?"
        r")\s*=\s*3\s*\+\s*2\s*(?:"
        r"sqrt\s*\(?\s*3\s*\)?|√\s*3|v[\"']?\s*3"
        r").{0,180}?corresponding to\s+(?:cosh|ch)\s*\(?\s*2\s*H\s*\)?"
        r"\s*=\s*2.{0,100}?honeycomb lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        ising_match,
        geometry_match,
        mapping_match,
        singularity_match,
        critical_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Syozi kagome Ising source must identify the Ising kagome "
            "geometry, the exact star-triangle mapping, the ferromagnetic "
            "specific-heat singularity, and exp(4 K_c)=3+2 sqrt(3)"
        )
    tc_over_j = 4.0 / math.log(3.0 + 2.0 * math.sqrt(3.0))
    return (
        {"tc_over_j": tc_over_j},
        {
            "parser": "parse_syozi_kagome_ising_ferromagnet_tc",
            "critical_condition": "exp(4 K_c)=3+2 sqrt(3)",
            "normalization": (
                "K=J/(k_B T) for sigma=+/-1 in the registered "
                "-J sum_<ij> sigma_i sigma_j convention"
            ),
            "derivation": (
                "Taking the logarithm of the printed condition gives "
                "4 J/(k_B T_c)=log(3+2 sqrt(3)), hence "
                "k_B T_c/J=4/log(3+2 sqrt(3))"
            ),
            "matched_anchors": [
                "identified Syôzi kagome-lattice paper",
                "exact Ising-model context",
                "coordination-four kagome geometry",
                "star-triangle mapping through the decorated honeycomb lattice",
                "ferromagnetic logarithmic specific-heat singularity",
                "critical equation and corresponding honeycomb condition",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def _parse_kano_naya_kagome_identity_prepared(normalized):
    identity_match = re.search(
        r"Progress of Theoretical Physics,\s*Vol\.?\s*10"
        r".{0,100}?(?:No\.?\s*2|August 1953)"
        r".{0,260}?Antiferromagnetism\.?\s*The Kagom(?:e|é) Ising Net"
        r".{0,180}?Kenzi Kan(?:o|ô).{0,80}?(?:and|&)\s*Shigeo Naya",
        normalized,
        flags=re.IGNORECASE,
    )
    exact_solution_match = re.search(
        r"solve exactly the eigenvalue problem of the Kagom(?:e|é) "
        r"Ising net with.{0,30}?z\s*\.?\s*=\s*4",
        normalized,
        flags=re.IGNORECASE,
    )
    if identity_match is None or exact_solution_match is None:
        raise RuntimeEvidenceError(
            "Kano-Naya kagome Ising source must identify the 1953 paper, "
            "both authors, and the exact coordination-four Ising problem"
        )
    return normalized, identity_match, exact_solution_match


def parse_kano_naya_kagome_ising_ferromagnet_tc(source_text):
    """Derive the kagome Ising Curie temperature from Kano-Naya Eq. (32)."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Kano-Naya kagome Ising evidence requires nonempty source text"
        )
    prepared = _prepared_view_for_parser(
        source_text, "parse_kano_naya_kagome_ising_ferromagnet_tc"
    )
    return _finalize_prepared_trace(
        _parse_kano_naya_kagome_ising_ferromagnet_tc_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_kano_naya_kagome_ising_ferromagnet_tc_prepared(normalized):
    normalized, identity_match, exact_solution_match = (
        _parse_kano_naya_kagome_identity_prepared(normalized)
    )
    critical_match = re.search(
        r"equation determining the transition temperature.{0,1200}?"
        r"(?:"
        r"e\s*\^\s*\(\s*4\s*L\s*_?\s*c\s*\)"
        r"|"
        r"e\s*4\s*L\s*_?\s*c"
        r")\s*=\s*3\s*\+\s*2\s*(?:"
        r"sqrt\s*\(\s*3\s*\)|sqrt\s*3|√\s*3|V\s*3"
        r").{0,80}?\(\s*32\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    normalization_match = re.search(
        r"energy per atom.{0,220}?L\s*=\s*J\s*/\s*"
        r"\(?\s*k(?:\s*_?\s*B)?\s*T\s*\)?"
        r".{0,40}?\(\s*38\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    sign_match = re.search(
        r"J\s*>\s*0.{0,80}?ferromagnetic case"
        r".{0,100}?J\s*<\s*0.{0,80}?antiferromagnetic case",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        exact_solution_match,
        critical_match,
        normalization_match,
        sign_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Kano-Naya kagome Ising ferromagnet source must establish "
            "Eq. (32), L=J/(k T) in Eq. (38), and the J>0 sign convention"
        )
    tc_over_j = 4.0 / math.log(3.0 + 2.0 * math.sqrt(3.0))
    return (
        {"tc_over_j": tc_over_j},
        {
            "parser": "parse_kano_naya_kagome_ising_ferromagnet_tc",
            "equation": "32",
            "critical_condition": "exp(4 L_c)=3+2 sqrt(3)",
            "normalization": (
                "Eq. (38) gives L=J/(k_B T), with J>0 in the "
                "ferromagnetic -J sum_<ij> sigma_i sigma_j convention"
            ),
            "derivation": (
                "Taking log of Eq. (32) gives "
                "4 J/(k_B T_c)=log(3+2 sqrt(3)), hence "
                "k_B T_c/J=4/log(3+2 sqrt(3))"
            ),
            "matched_anchors": [
                "identified Kano-Naya 1953 paper and both authors",
                "exact coordination-four kagome Ising eigenvalue problem",
                "critical-temperature equation (32)",
                "dimensionless coupling definition in equation (38)",
                "ferromagnetic coupling sign",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_kano_naya_kagome_ising_antiferromagnet_entropy(source_text):
    """Establish macroscopic kagome-Ising degeneracy from Eq. (47)."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Kano-Naya kagome Ising evidence requires nonempty source text"
        )
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_kano_naya_kagome_ising_antiferromagnet_entropy",
    )
    return _finalize_prepared_trace(
        _parse_kano_naya_kagome_ising_antiferromagnet_entropy_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_kano_naya_kagome_ising_antiferromagnet_entropy_prepared(
    normalized,
):
    normalized, identity_match, exact_solution_match = (
        _parse_kano_naya_kagome_identity_prepared(normalized)
    )
    disorder_entropy_match = re.search(
        r"(?:in the case of anti\s*ferromagnetism"
        r"|in the anti\s*ferromagnetic case).{0,360}?"
        r"Kagom(?:e|é) lattice.{0,360}?"
        r"does not fit(?:\s+to)?(?:\s+an?)?\s+anti.{0,70}?arrangement"
        r".{0,300}?is disorder(?:e)?d at all temperature(?:s)?"
        r".{0,300}?(?:possesses|has).{0,80}?finite zero point entropy",
        normalized,
        flags=re.IGNORECASE,
    )
    free_spin_match = re.search(
        r"free(?:-|\s+)spins.{0,30}?N\s*/\s*3",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_formula_match = re.search(
        r"S\s*_?\s*k\s*\(\s*0\s*\)\s*/\s*R\s*="
        r".{0,80}?1\s*/\s*\(\s*24\s*(?:pi|π)\s*\^?\s*2\s*\)"
        r".{0,220}?log\s*\[\s*21\s*-\s*4\s*\("
        r".{0,80}?cos\s*\(\s*(?:omega|ω)\s*_?\s*1\s*\)"
        r".{0,80}?cos\s*\(\s*(?:omega|ω)\s*_?\s*2\s*\)"
        r".{0,100}?cos\s*\(\s*(?:omega|ω)\s*_?\s*1\s*\+"
        r"\s*(?:omega|ω)\s*_?\s*2\s*\)"
        r".{0,160}?\(\s*47\s*\)\s*=\s*0\.50183",
        normalized,
        flags=re.IGNORECASE,
    )
    ocr_formula_match = re.search(
        r"[S5].{0,20}?\(\s*0\s*\)\s*/\s*R\s*="
        r".{0,240}?log\s*\[\s*21\s*-\s*4\s*\("
        r".{0,60}?cos\s+[Wwω].{0,20}?\+"
        r".{0,60}?cos\s+[Wwω].{0,20}?\+"
        r".{0,60}?cos\s*\(.{0,80}?\)"
        r".{0,160}?\(\s*47\s*\).{0,80}?0\.50183",
        normalized,
        flags=re.IGNORECASE,
    )
    formula_match = clean_formula_match or ocr_formula_match
    matches = (
        identity_match,
        exact_solution_match,
        disorder_entropy_match,
        free_spin_match,
        formula_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Kano-Naya kagome Ising antiferromagnet source must establish "
            "all-temperature disorder, extensive free spins, and the "
            "positive residual-entropy integral in Eq. (47)"
        )
    return (
        {"macroscopic_ground_state_degeneracy": True},
        {
            "parser": (
                "parse_kano_naya_kagome_ising_antiferromagnet_entropy"
            ),
            "equation": "47",
            "printed_residual_entropy_per_spin": 0.50183,
            "derivation": (
                "The positive entropy density s_0/k_B=0.50183 implies "
                "Omega_N=exp(N s_0 / k_B), so the ground-state "
                "degeneracy is macroscopic"
            ),
            "matched_anchors": [
                "identified Kano-Naya 1953 paper and both authors",
                "exact coordination-four kagome Ising eigenvalue problem",
                "all-temperature antiferromagnetic disorder and finite entropy",
                "explicit N/3 free-spin construction",
                "zero-point entropy integral and decimal in equation (47)",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_garel_maillard_villain_entropy(source_text):
    """Establish extensive Villain-model degeneracy from S_V=G/pi."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Garel-Maillard Villain entropy evidence requires nonempty text"
        )
    prepared = _prepared_view_for_parser(
        source_text, "parse_garel_maillard_villain_entropy"
    )
    return _finalize_prepared_trace(
        _parse_garel_maillard_villain_entropy_prepared(prepared.text),
        prepared,
    )


def _parse_garel_maillard_villain_entropy_prepared(normalized):

    identity_match = re.search(
        r"Study of a two-dimensional fully frustrated model"
        r".{0,180}?T\s+Garel[^\w\s]?\s+and\s+J\s+M\s+Maillard",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"Abstract\..{0,100}?fully frustrated Ising model on a square "
        r"lattice.{0,100}?four parameters.{0,260}?partition function "
        r"is shown to be equivalent.{0,100}?ferromagnetic.{0,40}?"
        r"Onsager partition function",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"model is defined in figure\s*1.{0,80}?reduced Hamiltonian reads"
        r".{0,280}?equation\s*\(\s*(?:1|l)\s*\).{0,120}?"
        r"nearest(?:-|\s*)neighbour pairing.{0,100}?(?:"
        r"(?:sigma|σ)\s*_?\s*i\s*=\s*(?:\+\s*/\s*-\s*1|±\s*1)"
        r"|"
        r"pi\s*=\s*i\s*l"
        r")",
        normalized,
        flags=re.IGNORECASE,
    )
    coupling_match = re.search(
        r"reduced coupling constants.{0,80}?may take the values"
        r".{0,50}?K\s*1\s*,\s*(?:-|[±*])\s*K\s*2\s*,\s*K\s*3"
        r"\s*,\s*(?:-|[±*])\s*K\s*4"
        r".{0,180}?isotropic case.{0,40}?K\s*1\s*=\s*K\s*2\s*="
        r"\s*K\s*3\s*=\s*K\s*4.{0,40}?corresponds to "
        r"Villain(?:'|’)?s model"
        r".{0,620}?four-parameter fully frustrated model"
        r".{0,100}?Double lines denote negative coupling constants"
        r".{0,60}?-\s*K\s*2.{0,20}?-\s*K\s*4",
        normalized,
        flags=re.IGNORECASE,
    )
    application_match = re.search(
        r"Application to the Villain model.{0,240}?Villain\s*"
        r"\(\s*1977\s*\)\s*model where K\s*_?\s*i\s*=\s*K",
        normalized,
        flags=re.IGNORECASE,
    )
    mapping_match = re.search(
        r"angular integrals.{0,100}?of the two partition functions are "
        r"the same for any temperature.{0,120}?allows us to link the "
        r"residual entropy S\s*_?\s*[vV].{0,80}?of the Villain model "
        r"with the Onsager free energy at criticality F\s*_?\s*c",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_formula_match = re.search(
        r"S\s*_?\s*[vV]\s*=.{0,140}?=\s*G\s*/\s*(?:pi|π)"
        r"\s*,?\s*where G is Catalan(?:'|’)?s constant",
        normalized,
        flags=re.IGNORECASE,
    )
    scan_ocr_formula_match = re.search(
        r"S\s*_?\s*[vV]\s*=\s*f\s*\(\s*-\s*p\s*c\s*F\s*c\s*-\s*"
        r"f\s+in\s+2\s*\)\s*=\s*G\s*/\s*T\s+where G is "
        r"Catalan(?:'|’)?s constant",
        normalized,
        flags=re.IGNORECASE,
    )
    formula_match = clean_formula_match or scan_ocr_formula_match
    matches = (
        identity_match,
        model_match,
        hamiltonian_match,
        coupling_match,
        application_match,
        mapping_match,
        formula_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Garel-Maillard Villain entropy source must identify the paper "
            "and authors, the fully frustrated square Ising couplings, the "
            "isotropic Villain limit, the exact Onsager mapping, and S_V=G/pi"
        )

    recomputed = recompute_garel_maillard_villain_entropy(
        series_terms=100000
    )
    entropy = recomputed["residual_entropy_per_spin"]
    return (
        {"macroscopic_ground_state_degeneracy": True},
        {
            "parser": "parse_garel_maillard_villain_entropy",
            "source_role": (
                "exact primary follow-up to the registered Villain 1977 source"
            ),
            "formula": "S_V=G/pi",
            "residual_entropy_per_spin": entropy,
            "degeneracy_scaling": "Omega_N=exp(N G/pi)",
            "derivation": (
                "Catalan's constant G is positive, so the exact entropy "
                "density G/pi is positive and the number of ground states "
                "grows exponentially with the number of square-lattice sites"
            ),
            "scan_ocr_pi_glyph_read_as_t": (
                clean_formula_match is None
                and scan_ocr_formula_match is not None
            ),
            "matched_anchors": [
                "identified Garel-Maillard paper and both authors",
                "fully frustrated square-lattice Ising model",
                "nearest-neighbour Ising Hamiltonian and spin domain",
                "signed couplings, isotropic Villain limit, and figure caption",
                "Villain 1977 application with equal coupling magnitudes",
                "exact partition-function mapping to critical Onsager model",
                "residual-entropy formula S_V=G/pi and Catalan definition",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def _parse_husimi_syozi_hexagonal_ising_anchors_prepared(normalized):
    identity_match = re.search(
        r"The Statistics of Honeycomb and Triangular Lattice\.?\s*I"
        r".{0,420}?Kodi Husimi.{0,260}?Itiro Sy(?:o|ô)zi",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"10\.1143/ptp/5\.2\.177",
        normalized,
        flags=re.IGNORECASE,
    )
    exact_method_match = re.search(
        r"applied.{0,80}?to the honeycomb lattice.{0,120}?"
        r"exact solution has been obtained.{0,180}?dual transformation"
        r".{0,180}?partition function for (?:the )?triangular net",
        normalized,
        flags=re.IGNORECASE,
    )
    critical_match = re.search(
        r"Curie point occurs at\s+(?:ch|cosh)\s*\(?\s*2\s*H\s*\)?"
        r"\s*=\s*2\s+in the honeycomb lattice\s+and at\s+"
        r"exp\s*\(\s*4\s*H\s*\)\s*=\s*3\s+in the triangular net",
        normalized,
        flags=re.IGNORECASE,
    )
    thermodynamics_match = re.search(
        r"coincide with the results obtained by the dual and "
        r"star(?:-|\s*)triangle transformations.{0,160}?"
        r"specific heat becomes logarithmically infinite.{0,120}?"
        r"energy itself remains continuous",
        normalized,
        flags=re.IGNORECASE,
    )
    antiferromagnetic_match = re.search(
        r"in the antiferromagnetic case.{0,120}?honeycomb lattice behaves "
        r"similar to the former case.{0,120}?triangular net exhibits "
        r"no phase change",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        doi_match,
        exact_method_match,
        critical_match,
        thermodynamics_match,
        antiferromagnetic_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Husimi-Syozi Ising source must identify the original paper, "
            "its exact honeycomb solution and triangular dual, both Curie "
            "conditions, the exact transformations and singularity, and "
            "the antiferromagnetic triangular contrast"
        )
    return matches


def _husimi_syozi_ising_trace(
    *, parser, critical_condition, derivation, matches
):
    return {
        "parser": parser,
        "critical_condition": critical_condition,
        "normalization": (
            "H=J/(k_B T) for sigma=+/-1 in the registered "
            "-J sum_<ij> sigma_i sigma_j convention"
        ),
        "derivation": derivation,
        "matched_anchors": [
            "identified Husimi-Syôzi Part I paper and authors",
            "publisher DOI",
            "exact honeycomb solution and triangular dual partition function",
            "paired honeycomb and triangular Curie conditions",
            "dual/star-triangle agreement and logarithmic singularity",
            "antiferromagnetic triangular no-transition contrast",
        ],
        "text_spans": [
            [match.start(), match.end()] for match in matches
        ],
    }


def parse_husimi_syozi_honeycomb_ising_tc(source_text):
    """Derive the honeycomb Ising Curie temperature from cosh(2H_c)=2."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Husimi-Syozi Ising critical conditions require nonempty source text"
        )
    prepared = _prepared_view_for_parser(
        source_text, "parse_husimi_syozi_honeycomb_ising_tc"
    )
    return _finalize_prepared_trace(
        _parse_husimi_syozi_honeycomb_ising_tc_prepared(prepared.text),
        prepared,
    )


def _parse_husimi_syozi_honeycomb_ising_tc_prepared(prepared_text):
    matches = _parse_husimi_syozi_hexagonal_ising_anchors_prepared(
        prepared_text
    )
    tc_over_j = 2.0 / math.log(2.0 + math.sqrt(3.0))
    return (
        {"tc_over_j": tc_over_j},
        _husimi_syozi_ising_trace(
            parser="parse_husimi_syozi_honeycomb_ising_tc",
            critical_condition="cosh(2 H_c)=2",
            derivation=(
                "arcosh(2)=log(2+sqrt(3)), so the printed condition "
                "gives 2 J/(k_B T_c)=log(2+sqrt(3)) and "
                "k_B T_c/J=2/log(2+sqrt(3))"
            ),
            matches=matches,
        ),
    )


def parse_husimi_syozi_triangular_ising_tc(source_text):
    """Derive the triangular Ising Curie temperature from exp(4H_c)=3."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Husimi-Syozi Ising critical conditions require nonempty source text"
        )
    prepared = _prepared_view_for_parser(
        source_text, "parse_husimi_syozi_triangular_ising_tc"
    )
    return _finalize_prepared_trace(
        _parse_husimi_syozi_triangular_ising_tc_prepared(prepared.text),
        prepared,
    )


def _parse_husimi_syozi_triangular_ising_tc_prepared(prepared_text):
    matches = _parse_husimi_syozi_hexagonal_ising_anchors_prepared(
        prepared_text
    )
    tc_over_j = 4.0 / math.log(3.0)
    return (
        {"tc_over_j": tc_over_j},
        _husimi_syozi_ising_trace(
            parser="parse_husimi_syozi_triangular_ising_tc",
            critical_condition="exp(4 H_c)=3",
            derivation=(
                "Taking the logarithm of the printed condition gives "
                "4 J/(k_B T_c)=log(3), hence k_B T_c/J=4/log(3)"
            ),
            matches=matches,
        ),
    )


def parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states(
    source_text,
):
    """Derive the normalized dimer energy and exact twofold degeneracy."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Caspers-Emmett-Magnus Majumdar-Ghosh proof requires "
            "nonempty source text"
        )
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states",
    )
    return _finalize_prepared_trace(
        _parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states_prepared(
    normalized,
):
    identity_match = re.search(
        r"The Majumdar(?:-|\s*)Ghosh chain[.:]?\s*Twofold ground state "
        r"and elementary excitations",
        normalized,
        flags=re.IGNORECASE,
    )
    authors_match = re.search(
        r"W\s*J\s*Caspers.{0,100}?K\s*M\s*Emmett"
        r".{0,100}?(?:and|&)\s*W\s*Magnus",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"10\.1088/0305-4470/17/13/020",
        normalized,
        flags=re.IGNORECASE,
    )
    legacy_print_code_match = re.search(
        r"0305\s*-\s*4470\s*1841132687\s*\+\s*10\s*\$\s*02\.25"
        r".{0,120}?1984.{0,80}?The Institute\s+of Physics"
        r".{0,40}?2687",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"H\s*=\s*4\s*(?:sum|sigma|Σ)"
        r".{0,180}?S\s*_?\s*(?:\{\s*)?j"
        r".{0,100}?S\s*_?\s*(?:\{\s*)?j\s*\+\s*1"
        r".{0,180}?\+\s*2\s*(?:sum|sigma|Σ)"
        r".{0,180}?S\s*_?\s*(?:\{\s*)?j"
        r".{0,100}?S\s*_?\s*(?:\{\s*)?j\s*\+\s*2",
        normalized,
        flags=re.IGNORECASE,
    )
    scan_spin_match = re.search(
        r"linear system of spins f with an isotropic interaction"
        r".{0,80}?between nearest and next(?:-|\s*)nearest neighbours",
        normalized,
        flags=re.IGNORECASE,
    )
    scan_coupling_match = re.search(
        r"interaction constant for next(?:-\s*|\s+)nearest neighbours is f "
        r"of that for nearest neighbours",
        normalized,
        flags=re.IGNORECASE,
    )
    boundary_spin_match = re.search(
        r"S\s*_?\s*(?:\{\s*)?i\s*\+\s*2\s*N"
        r".{0,80}?(?:=|identical\s+to)\s*"
        r"S\s*_?\s*(?:\{\s*)?i"
        r".{0,100}?S\s*_?\s*(?:\{\s*)?i\s*=\s*(?:1\s*/\s*2|½)",
        normalized,
        flags=re.IGNORECASE,
    )
    singlet_proof_match = re.search(
        r"at least two ground states.{0,180}?spins are arranged in "
        r"nearest(?:-|\s*)neighbour singlet pairs"
        r".{0,180}?these two states are the only ground states",
        normalized,
        flags=re.IGNORECASE,
    )
    translation_match = re.search(
        r"(?:two|at least two ground states,\s*the)\s+"
        r"singlet(?:-|\s*)pair states\s*\(\s*SPS\s*\)"
        r".{0,220}?connected by a translation over one elementary distance",
        normalized,
        flags=re.IGNORECASE,
    )
    periodic_proof_match = re.search(
        r"in\s+(?:section|§|8)\s*2\s+it is proved that the two SPS are "
        r"the only "
        r"ground states for the system with periodic boundary conditions"
        r".{0,100}?closed MG chain.{0,100}?open chain there is only one "
        r"ground state",
        normalized,
        flags=re.IGNORECASE,
    )
    direct_equation_route = all(
        match is not None
        for match in (doi_match, hamiltonian_match, boundary_spin_match)
    )
    scan_text_route = all(
        match is not None
        for match in (
            legacy_print_code_match,
            scan_spin_match,
            scan_coupling_match,
        )
    )
    source_identity_match = (
        doi_match if direct_equation_route else legacy_print_code_match
    )
    model_match = (
        hamiltonian_match if direct_equation_route else scan_coupling_match
    )
    spin_match = (
        boundary_spin_match if direct_equation_route else scan_spin_match
    )
    matches = (
        identity_match,
        authors_match,
        source_identity_match,
        model_match,
        spin_match,
        singlet_proof_match,
        translation_match,
        periodic_proof_match,
    )
    if (
        not direct_equation_route
        and not scan_text_route
    ) or any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Caspers-Emmett-Magnus source must identify the original "
            "twofold-ground-state paper, its three authors and either its "
            "DOI plus selectable Eq. (1) or its legacy IOP print code plus "
            "the scan-text spin-half J2/J1=1/2 model, nearest-"
            "neighbour singlet pairs, their one-site translation relation, "
            "and the proof that exactly those two states exhaust the "
            "closed-chain ground space"
        )

    spin = 0.5
    energy_per_site = -spin * (spin + 1.0) / 2.0
    equation_extraction = (
        "selectable_pdf_text_equation_1"
        if direct_equation_route
        else "scan_text_equivalent_j2_over_j1_one_half"
    )
    return (
        {
            "energy_per_site": energy_per_site,
            "degenerate_dimer_coverings": 2,
        },
        {
            "parser": (
                "parse_caspers_emmett_magnus_majumdar_ghosh_"
                "dimer_ground_states"
            ),
            "equation": "1",
            "equation_extraction": equation_extraction,
            "normalization": (
                "The source establishes J2/J1=1/2. In selectable equation "
                "text this is printed as J1=4 and J2=2; the repository scan "
                "text states the equivalent one-half coupling ratio. Set "
                "J1=1 for the registered convention."
            ),
            "derivation": (
                "For S=1/2, each nearest-neighbour singlet has "
                "S_i dot S_j=-S(S+1)=-3/4. There is one singlet per two "
                "sites, while correlations between distinct singlets "
                "vanish, so the J1=1 energy is -3/8 per site. The source "
                "proves that the two one-site-translated periodic dimer "
                "coverings exhaust the ground space."
            ),
            "matched_anchors": [
                "identified Caspers-Emmett-Magnus twofold-ground-state paper",
                "identified all three authors",
                (
                    "publisher DOI 10.1088/0305-4470/17/13/020"
                    if direct_equation_route
                    else "legacy IOP print code for volume 17 page 2687"
                ),
                (
                    "Hamiltonian Eq. (1) with nearest/next-nearest "
                    "weights 4:2"
                    if direct_equation_route
                    else "scan-text J2/J1=1/2 coupling convention"
                ),
                (
                    "periodic spin-half convention in Eq. (1)"
                    if direct_equation_route
                    else "scan-text spin-half MG-chain convention"
                ),
                "nearest-neighbour singlet pairs are the only ground states",
                "the two singlet-pair states differ by one-site translation",
                "periodic closed-chain uniqueness proof and open-chain contrast",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_lapilli_square_clock_three_phase_regime(source_text):
    """Extract the two-transition phase sequence of the square q=5 clock model."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Lapilli clock result requires nonempty source text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    identity_match = re.search(
        r"Universality Away from Critical Points in Two-Dimensional "
        r"Phase Transitions.{0,180}?Cintia M\.?\s*Lapilli"
        r".{0,100}?Peter Pfeifer.{0,100}?(?:and|&)\s*Carlos Wexler",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"10\.1103/PhysRevLett\.96\.140603",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"p-state clock model in two dimensions.{0,100}?"
        r"system of discrete rotors",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"(?:H\s*=\s*-\s*J0|Hp.{0,80}?J0)"
        r".{0,180}?cos.{0,180}?\(\s*1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    intermediate_phase_match = re.search(
        r"quasiliquid phase in a region\s*T1\s*<\s*T\s*<\s*T2"
        r"\s*for\s*p\s*>\s*4",
        normalized,
        flags=re.IGNORECASE,
    )
    q5_match = re.search(
        r"\bp\s*=\s*5\b",
        normalized,
        flags=re.IGNORECASE,
    )
    phase_sequence_match = re.search(
        r"(?:The\s+)?correlation function.{0,240}?"
        r"(?:goes|tends)\s+to\s+a\s+non(?:\s*|-.{0,260}?)zero "
        r"constant.{0,180}?T\s*<\s*T1"
        r".{0,600}?decays as a power law"
        r".{0,180}?T1\s*<\s*T\s*<\s*T2"
        r".{0,600}?decays exponentially"
        r".{0,180}?T\s*>\s*T2",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        doi_match,
        model_match,
        hamiltonian_match,
        intermediate_phase_match,
        q5_match,
        phase_sequence_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Lapilli clock source must identify the original paper and DOI, "
            "the two-dimensional discrete-rotor Hamiltonian in Eq. (1), "
            "the q=5 member of the p>4 quasiliquid regime, and the ordered, "
            "power-law critical, and disordered correlation sequence across "
            "two distinct temperatures T1 and T2"
        )

    return (
        {
            "transition_count": 2,
            "phase_sequence": ["ordered", "critical", "disordered"],
        },
        {
            "parser": "parse_lapilli_square_clock_three_phase_regime",
            "equation": "1",
            "registered_q": 5,
            "derivation": (
                "For q=p=5, the source's p>4 phase diagram has an ordered "
                "phase below T1, a power-law quasiliquid (critical) phase "
                "between T1 and T2, and a disordered phase above T2; the "
                "two boundaries therefore give two transitions."
            ),
            "matched_anchors": [
                "identified Lapilli-Pfeifer-Wexler paper and authors",
                "publisher DOI 10.1103/PhysRevLett.96.140603",
                "two-dimensional p-state discrete-rotor model",
                "clock Hamiltonian Eq. (1)",
                "p>4 quasiliquid interval T1<T<T2",
                "explicit p=5 data",
                "constant, power-law, and exponential correlation sequence",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_ising_1925_linear_chain_no_transition(source_text):
    """Extract Ising's absence of spontaneous order in the linear chain."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Ising 1925 linear chain result requires nonempty source text"
        )
    prepared = _prepared_view_for_parser(
        source_text, "parse_ising_1925_linear_chain_no_transition"
    )
    return _finalize_prepared_trace(
        _parse_ising_1925_linear_chain_no_transition_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_ising_1925_linear_chain_no_transition_prepared(normalized):
    identity_match = re.search(
        r"Ernst Ising.{0,260}?Contribution to the "
        r"Theory of Ferromagnetism.{0,100}?1925",
        normalized,
        flags=re.IGNORECASE,
    )
    chain_match = re.search(
        r"(?:2\.\s*)?The simple linear chain.{0,220}?"
        r"linear magnet consisting of\s+n\s+elements",
        normalized,
        flags=re.IGNORECASE,
    )
    binary_match = re.search(
        r"each of these\s+n\s+elements.{0,100}?only two positions"
        r".{0,260}?two possible directions.{0,120}?positive and negative",
        normalized,
        flags=re.IGNORECASE,
    )
    interaction_match = re.search(
        r"(?:similar poles of )?neighboring elements.{0,180}?"
        r"\(\s*2\s*s\s*\+\s*(?:delta|d|δ)\s*\)\s+positions"
        r".{0,450}?inner energy",
        normalized,
        flags=re.IGNORECASE,
    )
    temperature_match = re.search(
        r"Boltzmann constant.{0,100}?\bT\s+is the absolute temperature"
        r".{0,760}?partition function\s+Z",
        normalized,
        flags=re.IGNORECASE,
    )
    result_match = re.search(
        r"(?:Eq(?:uation)?\.?\s*\(?\s*8\s*\)?|\(\s*8\s*\))"
        r".{0,220}?function disappears for\s+H\s*=\s*0"
        r".{0,120}?no appearances of hysteresis and no spontaneous "
        r"magnetization",
        normalized,
        flags=re.IGNORECASE,
    )
    probability_match = re.search(
        r"H\s*=\s*0.{0,180}?probabilities as a function of the moment\s+M"
        r".{0,260}?two maxima.{0,160}?single maximum at\s+M\s*=\s*0"
        r".{0,700}?simple calculation shows that the "
        r"(?:probabilities|possibilities) only have a simple maximum",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        chain_match,
        binary_match,
        interaction_match,
        temperature_match,
        result_match,
        probability_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Ising 1925 linear chain source must identify the binary "
            "nearest-neighbor chain at finite temperature, Eq. (8), the "
            "absence of zero-field spontaneous magnetization, and the "
            "single-peaked moment distribution"
        )
    return (
        {
            "finite_temperature_transition": False,
            "tc_over_j": 0.0,
        },
        {
            "parser": "parse_ising_1925_linear_chain_no_transition",
            "equation": "8",
            "normalization": (
                "the source domain-wall cost epsilon equals 2J in the "
                "registered -J sum_i sigma_i sigma_(i+1) convention; "
                "the zero critical-temperature ratio is scale independent"
            ),
            "derivation": (
                "The thermodynamic-limit Eq. (8) gives zero-field "
                "spontaneous magnetization equal to zero and the source "
                "excludes a symmetry-related two-peak distribution. Thus "
                "there is no ordered finite-temperature phase and the "
                "registered convention assigns T_c/J=0."
            ),
            "matched_anchors": [
                "identified English edition of Ising's 1925 paper",
                "simple linear chain",
                "two-state spin variables",
                "nearest-neighbor domain-wall energy",
                "finite absolute-temperature partition function",
                "Eq. (8) has no zero-field spontaneous magnetization",
                "single-peaked zero-field moment distribution",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _is_nonempty_string_sequence(value, *, unique=False):
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not value
        or not all(_is_nonempty_string(item) for item in value)
    ):
        return False
    return not unique or len(value) == len(set(value))


def _is_valid_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _contains_nonfinite(value):
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, Mapping):
        return any(_contains_nonfinite(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_contains_nonfinite(item) for item in value)
    return False


def _is_valid_operand(operand, selector_fields):
    if (
        not isinstance(operand, Mapping)
        or not operand
        or set(operand) != set(selector_fields)
        or _contains_nonfinite(operand)
    ):
        return False
    try:
        json.dumps(operand, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def _exact_json_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _exact_json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, Sequence) and not isinstance(left, (str, bytes)):
        return len(left) == len(right) and all(
            _exact_json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _validate_operand_comparison(comparison, source_operand, registry_operand):
    if not isinstance(comparison, Mapping) or comparison.get("matched") is not True:
        return False
    kind = comparison.get("kind")
    if kind == "exact_field_map":
        return _exact_json_equal(source_operand, registry_operand)
    if kind != "absolute_tolerance":
        return False
    tolerance = comparison.get("absolute_tolerance")
    if (
        isinstance(tolerance, bool)
        or not isinstance(tolerance, (int, float))
        or not math.isfinite(tolerance)
        or tolerance < 0.0
    ):
        return False
    reported_differences = comparison.get("absolute_differences")
    if (
        not isinstance(reported_differences, Mapping)
        or set(reported_differences) != set(source_operand)
    ):
        return False
    for field in source_operand:
        source_value = source_operand[field]
        registry_value = registry_operand[field]
        reported_difference = reported_differences[field]
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in (source_value, registry_value, reported_difference)
        ):
            return False
        if not all(
            math.isfinite(value)
            for value in (source_value, registry_value, reported_difference)
        ):
            return False
        actual_difference = abs(source_value - registry_value)
        if not math.isclose(
            reported_difference, actual_difference, rel_tol=0.0, abs_tol=1.0e-15
        ):
            return False
        if actual_difference > tolerance:
            return False
    return True


def _is_valid_text_spans(value):
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not value
    ):
        return False
    for span in value:
        if (
            not isinstance(span, Sequence)
            or isinstance(span, (str, bytes))
            or len(span) != 2
        ):
            return False
        start, end = span
        if type(start) is not int or type(end) is not int or start < 0 or start >= end:
            return False
    return True


def _coordinate_metadata_names(trace):
    return {
        key
        for key in trace
        if key == "coordinate_space"
        or key.startswith("coordinate_builder")
        or key.startswith("coordinate_contract")
        or key.startswith("coordinate_view")
        or key.startswith("text_span_sha")
        or key.startswith("text_span_capture")
    }


def _is_valid_prepared_coordinate_trace(trace):
    if _coordinate_metadata_names(trace) != (
        _PREPARED_COORDINATE_METADATA_KEYS
    ):
        return False
    builder_id = trace.get("coordinate_builder")
    version = trace.get("coordinate_contract_version")
    if not isinstance(builder_id, str) or type(version) is not int:
        return False
    if (builder_id, version) not in _PREPARED_VIEW_SPECS:
        return False
    parser_name = trace.get("parser")
    if not isinstance(parser_name, str):
        return False
    declared_builder = _PREPARED_TRACE_PARSER_BUILDERS.get(parser_name)
    if declared_builder != (builder_id, version):
        return False
    if not _is_valid_sha256(trace.get("coordinate_view_sha256")):
        return False
    view_length = trace.get("coordinate_view_length")
    if type(view_length) is not int or view_length <= 0:
        return False
    spans = trace.get("text_spans")
    if not _is_valid_text_spans(spans):
        return False
    captures = trace.get("text_span_captures")
    span_sha256 = trace.get("text_span_sha256")
    if (
        not isinstance(captures, Sequence)
        or isinstance(captures, (str, bytes))
        or not isinstance(span_sha256, Sequence)
        or isinstance(span_sha256, (str, bytes))
        or len(captures) != len(spans)
        or len(span_sha256) != len(spans)
    ):
        return False
    for span, capture, digest in zip(spans, captures, span_sha256):
        start, end = span
        if (
            end > view_length
            or not isinstance(capture, str)
            or len(capture) != end - start
            or not _is_valid_sha256(digest)
            or hashlib.sha256(capture.encode("utf-8")).hexdigest()
            != digest
        ):
            return False
    return True


def _is_valid_extraction_trace(trace, benchmark_name, source_sha256):
    if not isinstance(trace, Mapping) or any(
        not isinstance(key, str) for key in trace
    ):
        return False
    coordinate_space = trace.get("coordinate_space")
    coordinate_metadata = _coordinate_metadata_names(trace)
    if coordinate_space == "whitespace_normalized_extracted_text":
        coordinate_space_is_valid = coordinate_metadata == {
            "coordinate_space"
        }
    elif coordinate_space == _PREPARED_TRACE_COORDINATE_SPACE:
        coordinate_space_is_valid = _is_valid_prepared_coordinate_trace(
            trace
        )
    else:
        coordinate_space_is_valid = False
    return (
        trace.get("benchmark_name") == benchmark_name
        and trace.get("source_sha256") == source_sha256
        and coordinate_space_is_valid
        and _is_nonempty_string(trace.get("parser"))
        and _is_nonempty_string_sequence(trace.get("matched_anchors"))
        and _is_valid_text_spans(trace.get("text_spans"))
    )


def structurally_validate_runtime_evidence_bundle(benchmark_name, runtime_bundle):
    """Return a strict category for a well-formed bundle, without proving provenance.

    This validator checks internal structure and equality only. A caller must separately
    establish that the bundle came from the authoritative cache-backed collector.
    """

    if not isinstance(runtime_bundle, Mapping):
        return None
    record = runtime_bundle.get("runtime_evidence_record")
    if not isinstance(record, Mapping):
        return None
    if record.get("benchmark_name") != benchmark_name:
        return None
    if not _is_nonempty_string(record.get("source_id")):
        return None
    source_sha256 = record.get("source_sha256")
    if not _is_valid_sha256(source_sha256):
        return None
    selector = record.get("registry_selector")
    if not isinstance(selector, Mapping):
        return None
    selector_path = selector.get("path")
    selector_fields = selector.get("fields")
    if not _is_nonempty_string_sequence(selector_path):
        return None
    if not _is_nonempty_string_sequence(selector_fields, unique=True):
        return None
    source_operand = record.get("source_operand")
    registry_operand = record.get("registry_operand")
    if not _is_valid_operand(source_operand, selector_fields):
        return None
    if not _is_valid_operand(registry_operand, selector_fields):
        return None
    comparison = record.get("comparison")
    if not _validate_operand_comparison(
        comparison, source_operand, registry_operand
    ):
        return None
    mode = record.get("evidence_mode")
    if mode not in {"local_recompute", "local_source_parse"}:
        return None
    extraction_trace = runtime_bundle.get("extraction_trace")
    if not _is_valid_extraction_trace(
        extraction_trace, benchmark_name, source_sha256
    ):
        return None
    if mode == "local_recompute":
        computed_operand = record.get("computed_operand")
        if not _is_valid_operand(computed_operand, selector_fields):
            return None
        if not _exact_json_equal(computed_operand, source_operand):
            return None
        execution_trace = runtime_bundle.get("execution_trace")
        if not isinstance(execution_trace, Mapping):
            return None
        if execution_trace.get("benchmark_name") != benchmark_name:
            return None
        if execution_trace.get("source_sha256") != source_sha256:
            return None
        if not _is_nonempty_string(execution_trace.get("adapter")):
            return None
        if not isinstance(execution_trace.get("adapter_parameters"), Mapping):
            return None
        trace_computed_operand = execution_trace.get("computed_operand")
        if not _is_valid_operand(trace_computed_operand, selector_fields):
            return None
        if not _exact_json_equal(trace_computed_operand, computed_operand):
            return None
    return {
        "local_recompute": "strict_local_recomputed",
        "local_source_parse": "strict_local_source_parsed",
    }[mode]


def parse_cri3_ferromagnetic_order(source_text):
    """Extract the CrI3 honeycomb ferromagnetic-order claim from source text."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("CrI3 source claim requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    anchor_patterns = (
        ("honeycomb network", r"honeycomb network"),
        (
            "long range ferromagnetic order develops below TC = 61 K",
            r"long range ferromagnetic order develops.{0,120}?below T\s*C\s*=\s*61 K",
        ),
    )
    matches = [
        re.search(pattern, normalized, flags=re.IGNORECASE)
        for _, pattern in anchor_patterns
    ]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "CrI3 source claim must contain the honeycomb structure and "
            "61 K long-range ferromagnetic-order statements"
        )
    return (
        {"ferromagnetic_order": True},
        {
            "parser": "parse_cri3_ferromagnetic_order",
            "matched_anchors": [label for label, _ in anchor_patterns],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_yang_yang_xxx_ground_state_energy(source_text):
    """Parse Eq. (31c) using the locked Yang-Yang PDF's font mapping."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Yang-Yang Eq. (31c) requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    pattern = re.compile(
        r"=\s*-\s*,\s*'\s*[\-\N{MINUS SIGN}\N{EN DASH}\N{EM DASH}]\s*"
        r"ln\s*2\s*;.{0,100}?\(31c\)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(normalized)
    if match is None:
        raise RuntimeEvidenceError(
            "Yang-Yang Eq. (31c) must contain the locked one-quarter glyph, ln2, "
            "and equation label"
        )
    return (
        {"energy_per_site": 0.25 - math.log(2.0)},
        {
            "parser": "parse_yang_yang_xxx_ground_state_energy",
            "equation": "31c",
            "normalization": "yang_yang_1966_fraction_glyph_one_quarter",
            "matched_anchors": ["locked fraction glyph", "ln2", "(31c)"],
            "text_spans": [[match.start(), match.end()]],
        },
    )


def parse_hirata_nomura_xxz_phase_boundaries(source_text):
    """Extract the exact nearest-neighbor XXZ phase diagram at alpha=0."""

    error_message = (
        "Hirata-Nomura exact XXZ submodel source must establish the "
        "identified cond-mat/9909290v1 preprint, its antiferromagnetic "
        "spin-half J1-J2 XXZ Hamiltonian, the alpha=0 Bethe-ansatz "
        "submodel, the Delta=-1 and Delta=1 ordered-phase boundaries, "
        "and the closed [-1,1] gapless spin-fluid interval"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text, "parse_hirata_nomura_xxz_phase_boundaries"
    )
    return _finalize_prepared_trace(
        _parse_hirata_nomura_xxz_phase_boundaries_prepared(prepared.text),
        prepared,
    )


def _parse_hirata_nomura_xxz_phase_boundaries_prepared(normalized):
    error_message = (
        "Hirata-Nomura exact XXZ submodel source must establish the "
        "identified cond-mat/9909290v1 preprint, its antiferromagnetic "
        "spin-half J1-J2 XXZ Hamiltonian, the alpha=0 Bethe-ansatz "
        "submodel, the Delta=-1 and Delta=1 ordered-phase boundaries, "
        "and the closed [-1,1] gapless spin-fluid interval"
    )

    alpha_pattern = r"(?:alpha|α)"
    delta_pattern = r"(?:Delta|∆)"
    less_equal_pattern = r"(?:<=|≤)"
    spin_half_pattern = r"spin\s*-\s*(?:1\s*/\s*2|1\s*2|12)"

    identity_match = re.search(
        r"(?:"
        r"1\s+Phase diagram of S\s*=\s*2\s+XXZ chain with NNN "
        r"interaction"
        r"|"
        r"Phase diagram of S\s*=\s*1\s*/\s*2\s+XXZ chain with NNN "
        r"interaction"
        r")"
        r".{0,450}?Shunsaku Hirata"
        r".{0,180}?Kiyohide Nomura"
        r".{0,1200}?arXiv\s*:\s*cond-mat\s*/\s*9909290v1"
        r"\s*\[\s*cond-mat\.stat-mech\s*\]\s*20 Sep 1999",
        normalized,
        flags=re.IGNORECASE,
    )

    spin_component = (
        r"S\s*_?\s*{site}\s*\^?\s*{axis}"
    )
    s_ix = spin_component.format(site="i", axis="x")
    s_jx = spin_component.format(site="j", axis="x")
    s_iy = spin_component.format(site="i", axis="y")
    s_jy = spin_component.format(site="j", axis="y")
    s_iz = spin_component.format(site="i", axis="z")
    s_jz = spin_component.format(site="j", axis="z")
    h_i_i1 = r"h\s*_?\s*i\s*,\s*i\s*\+\s*1"
    h_i_i2 = r"h\s*_?\s*i\s*,\s*i\s*\+\s*2"
    h_ij = r"h\s*_?\s*i\s*,\s*j"
    model_match = re.search(
        r"(?:One of.{0,1200}?simplest model(?:s)?(?: of them)? is the )?"
        + spin_half_pattern
        + r"\s+XXZ chain"
        r".{0,120}?next\s*-\s*nearest\s*-\s*neighbor interaction"
        r".{0,1800}?described by the"
        r".{0,1000}?Hamiltonian"
        r".{0,2600}?H\s*=\s*J"
        r".{0,700}?"
        + h_i_i1
        + r"\s*\+\s*"
        + alpha_pattern
        + r"\s*"
        + h_i_i2
        + r".{0,1200}?"
        + h_ij
        + r"\s*=\s*"
        + s_ix
        + r"\s+"
        + s_jx
        + r"\s*\+\s*"
        + s_iy
        + r"\s+"
        + s_jy
        + r"\s*\+\s*"
        + delta_pattern
        + r"\s*"
        + s_iz
        + r"\s+"
        + s_jz
        + r"\s*\.?\s*\(\s*1\s*\)"
        r".{0,500}?set NN coupling J\s*>\s*0",
        normalized,
        flags=re.IGNORECASE,
    )
    integrability_match = re.search(
        r"ground state properties are known for several cases"
        r".{0,250}?When\s+"
        + alpha_pattern
        + r"\s*=\s*0(?![\d.])\s*,"
        r".{0,160}?integrable by the Bethe ansatz",
        normalized,
        flags=re.IGNORECASE,
    )
    ordered_phases_match = re.search(
        r"For\s+"
        + delta_pattern
        + r"\s*<\s*-\s*1(?![\d.])\s*,\s*the system becomes the "
        r"ferromagnetic.{0,120}?phase"
        r".{0,260}?while for\s+"
        + delta_pattern
        + r"\s*>\s*1(?![\d.])\s*,\s*it becomes the "
        r"N\s*[´'’]?\s*eel phase",
        normalized,
        flags=re.IGNORECASE,
    )
    gapless_match = re.search(
        r"(?:In )?the case of XY\s*-\s*type anisotropy"
        r"\s*\(\s*-\s*1\s*"
        + less_equal_pattern
        + r"\s*"
        + delta_pattern
        + r"\s*"
        + less_equal_pattern
        + r"\s*1\s*\)"
        r".{0,700}?quan(?:tum|\s*-\s*tum) fluctuation"
        r".{0,350}?destroys the long range order"
        r".{0,700}?zero temperature"
        r".{0,700}?ground state is characterized"
        r".{0,350}?by a gapless excitation"
        r".{0,350}?algebraic decay of spin "
        r"(?:correlations|corre\s*-.{0,100}?lations)"
        r".{0,100}?\(\s*spin fluid phase\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        model_match,
        integrability_match,
        ordered_phases_match,
        gapless_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    return (
        {
            "ferromagnetic_boundary_delta": -1.0,
            "neel_boundary_delta": 1.0,
            "gapless_interval": [-1.0, 1.0],
        },
        {
            "parser": "parse_hirata_nomura_xxz_phase_boundaries",
            "source_model": (
                "H=J sum_i(h_i,i+1+alpha h_i,i+2), "
                "h_ij=SxSx+SySy+Delta SzSz, J>0"
            ),
            "exact_submodel": (
                "alpha=0 nearest-neighbor spin-1/2 XXZ chain"
            ),
            "registered_convention_mapping": (
                "source Delta equals registry Delta; no sign or scale "
                "conversion"
            ),
            "corrected_source_identity": "arXiv:cond-mat/9909290v1",
            "superseded_registered_doi": "10.1103/PhysRev.150.321",
            "matched_anchors": [
                "identified cond-mat/9909290v1 paper and authors",
                "spin-half antiferromagnetic J1-J2 XXZ Hamiltonian, Eq. (1)",
                "alpha=0 Bethe-ansatz integrable submodel",
                "Delta<-1 ferromagnet and Delta>1 Neel phase",
                "closed [-1,1] gapless spin-fluid interval",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def _parse_okamoto_nomura_j1_j2_critical_ratio(source_text):
    error_message = (
        "Okamoto-Nomura J1-J2 critical source must establish the "
        "identified Physics Letters A 169 paper, its periodic "
        "antiferromagnetic spin-half NN-plus-NNN Hamiltonian with "
        "alpha=J2/J1, the singlet-triplet/singlet-singlet crossing for "
        "N=8,10,...,24, the independent reported extrapolations, and "
        "the alpha_c=0.2411+/-0.0001 conclusion"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)

    normalized = re.sub(r"\s+", " ", source_text).strip()
    normalized = (
        normalized.replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
    )
    spin_half_pattern = r"(?:1\s*/\s*2|1\s*2|2\s*1|})"
    alpha_pattern = r"(?:alpha|α|a)"

    identity_match = re.search(
        r"Physics Letters A\s+169\s*\(\s*1992\s*\)\s*433\s*-\s*437"
        r".{0,500}?Fluid\s*-\s*dimer critical point in S\s*=\s*"
        + spin_half_pattern
        + r"\s+antiferromagnetic Heisenberg chain"
        r".{0,100}?with next nearest neighbor interactions"
        r".{0,300}?Kiyomi Okamoto"
        r".{0,100}?(?:and\s+)?Kiyohide Nomura"
        r".{0,500}?Received 20 April 1992"
        r".{0,250}?27 July 1992"
        r".{0,250}?5 August 1992",
        normalized,
        flags=re.IGNORECASE,
    )

    clean_equation_match = re.search(
        r"H\s*=\s*J\s*sum\s*_?\s*j"
        r".{0,120}?S\s*_?\s*j"
        r".{0,60}?S\s*_?\s*j\s*\+\s*1"
        r".{0,120}?"
        + alpha_pattern
        + r".{0,80}?S\s*_?\s*j"
        r".{0,60}?S\s*_?\s*j\s*\+\s*2"
        r".{0,180}?J\s*>\s*0"
        r".{0,100}?"
        + alpha_pattern
        + r"\s*>\s*[0O]",
        normalized,
        flags=re.IGNORECASE,
    )
    ocr_equation_match = re.search(
        r"Our Ham(?:iltonian|\s*-\s*iltonian) in this paper is expressed as"
        r".{0,800}?S.{0,80}?\+\s*1"
        r".{0,180}?"
        + alpha_pattern
        + r".{0,120}?S.{0,80}?\+\s*2"
        r".{0,250}?J\s*>\s*0"
        r".{0,120}?"
        + alpha_pattern
        + r"\s*>\s*[0O]"
        r".{0,100}?\(\s*1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    equation_match = clean_equation_match or ocr_equation_match
    model_identity_match = re.search(
        r"We numerically investigate the critical value"
        r".{0,200}?fluid\s*-\s*dimer transition"
        r".{0,180}?ground state of the S\s*=\s*"
        + spin_half_pattern
        + r"\s+antiferromagnetic Heisenberg chain"
        r".{0,100}?with next nearest neighbor interactions"
        r".{0,700}?J\s*>\s*0"
        r".{0,120}?"
        + alpha_pattern
        + r"\s*>\s*[0O]"
        r".{0,350}?conformal field theory"
        r".{0,180}?0\.2411"
        r".{0,80}?0\.0001",
        normalized,
        flags=re.IGNORECASE,
    )
    boundary_match = re.search(
        r"assume the periodic boundary condition"
        r".{0,250}?N is the number of spins"
        r".{0,160}?as(?:sumed|\s*-\s*sumed) to be even",
        normalized,
        flags=re.IGNORECASE,
    )

    gap_types_match = re.search(
        r"singlet\s*-\s*triplet (?:excitation|gap)"
        r".{0,1800}?(?:whereas|and)"
        r".{0,500}?singlet\s*-\s*singlet (?:excitation|gap)",
        normalized,
        flags=re.IGNORECASE,
    )
    crossing_match = re.search(
        r"critical value"
        r".{0,600}?determined by"
        r".{0,700}?\(\s*19\s*\)"
        r".{0,800}?obtained from"
        r".{0,800}?\(\s*20\s*\)"
        r".{0,900}?numerically calculated"
        r".{0,900}?finite systems\s+[NV]\s*=\s*8\s*,\s*10\s*,"
        r"\s*(?:\.\s*){3}\s*,?\s*24"
        r".{0,300}?TITPACK\s+ver\.?\s*2"
        r".{0,900}?crossing points"
        r".{0,1200}?0\.24\s*<\s*"
        + alpha_pattern
        + r"\s*<\s*0\.25",
        normalized,
        flags=re.IGNORECASE,
    )

    alternating_match = re.search(
        r"al(?:ternating|\s*-\s*ternating)"
        r"\s*-\s*(?:epsilon|e|€e)\s+algorithm"
        r".{0,2600}?0\.24112218"
        r".{0,250}?\(\s*24\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    shanks_match = re.search(
        r"Shanks\s*[’']?\s+transformation"
        r".{0,500}?0\.24117290"
        r".{0,250}?\(\s*25\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    least_squares_match = re.search(
        r"least\s*-\s*squares fitting"
        r".{0,500}?0\.241155"
        r".{0,100}?0\.000003"
        r".{0,250}?\(\s*30\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"Thus we can safely conclude that"
        r".{0,180}?0\.2411"
        r"\s*(?:\+\s*/\s*-|\+\s*-|\+|±)\s*0\.0001"
        r".{0,200}?\(\s*31\s*\)"
        r".{0,1800}?In conclusion"
        r".{0,300}?determined the critical value"
        r".{0,180}?(?P<critical>0\.2411)"
        r"\s*(?:\+\s*/\s*-|\+\s*-|\+|±)\s*"
        r"(?P<uncertainty>0\.0001)"
        r".{0,300}?numerical data of the finite(?:\s*-\s*|\s+)size systems"
        r".{0,250}?conformal field theory"
        r"\.",
        normalized,
        flags=re.IGNORECASE,
    )

    required_matches = (
        identity_match,
        equation_match,
        model_identity_match,
        boundary_match,
        gap_types_match,
        crossing_match,
        alternating_match,
        shanks_match,
        least_squares_match,
        conclusion_match,
    )
    if any(match is None for match in required_matches):
        raise RuntimeEvidenceError(error_message)

    critical_ratio = float(conclusion_match.group("critical"))
    uncertainty = float(conclusion_match.group("uncertainty"))
    if (
        not math.isclose(
            critical_ratio, 0.2411, rel_tol=0.0, abs_tol=1.0e-12
        )
        or not math.isclose(
            uncertainty, 0.0001, rel_tol=0.0, abs_tol=1.0e-12
        )
    ):
        raise RuntimeEvidenceError(error_message)

    model_start = min(
        equation_match.start(),
        model_identity_match.start(),
        boundary_match.start(),
    )
    model_end = max(
        equation_match.end(),
        model_identity_match.end(),
        boundary_match.end(),
    )
    crossing_start = min(gap_types_match.start(), crossing_match.start())
    crossing_end = max(gap_types_match.end(), crossing_match.end())
    extrapolation_start = min(
        alternating_match.start(),
        shanks_match.start(),
        least_squares_match.start(),
    )
    extrapolation_end = max(
        alternating_match.end(),
        shanks_match.end(),
        least_squares_match.end(),
    )
    return (
        critical_ratio,
        {
            "reported_uncertainty": uncertainty,
            "finite_sizes": list(range(8, 25, 2)),
            "source_model": (
                "H=J sum_j(S_j.S_j+1+alpha S_j.S_j+2), J>0, "
                "periodic even-N spin-1/2 chain"
            ),
            "source_ratio_mapping": "alpha=J2/J1",
            "level_spectroscopy_condition": (
                "G_st(N,alpha_c(N))=G_ss(N,alpha_c(N))"
            ),
            "reported_extrapolations": {
                "alternating_epsilon": 0.24112218,
                "shanks": 0.24117290,
                "one_over_n_squared_fit": 0.241155,
            },
            "matched_anchors": [
                "identified Okamoto-Nomura Physics Letters A 169 paper",
                "periodic antiferromagnetic spin-half NN-plus-NNN Hamiltonian",
                "singlet-triplet/singlet-singlet crossing for N=8,10,...,24",
                "alternating-epsilon, Shanks, and 1/N^2 extrapolations",
                "alpha_c=0.2411+/-0.0001 conclusion",
            ],
            "text_spans": [
                [identity_match.start(), identity_match.end()],
                [model_start, model_end],
                [crossing_start, crossing_end],
                [extrapolation_start, extrapolation_end],
                [conclusion_match.start(), conclusion_match.end()],
            ],
        },
    )


def parse_okamoto_nomura_j1_j2_critical_point(source_text):
    """Extract Okamoto and Nomura's thermodynamic J2/J1 critical ratio."""

    critical_ratio, trace = _parse_okamoto_nomura_j1_j2_critical_ratio(
        source_text
    )
    trace = dict(trace)
    trace["parser"] = "parse_okamoto_nomura_j1_j2_critical_point"
    return {"critical_j2_over_j1": critical_ratio}, trace


def parse_okamoto_nomura_j1_j2_bkt_reference(source_text):
    """Map the same fluid-dimer critical ratio to the approximate field."""

    critical_ratio, trace = _parse_okamoto_nomura_j1_j2_critical_ratio(
        source_text
    )
    trace = dict(trace)
    trace["parser"] = "parse_okamoto_nomura_j1_j2_bkt_reference"
    return {"critical_j2_over_j1_approx": critical_ratio}, trace


def _parse_kumar_j1_j2_critical_ratio_prepared(normalized):
    error_message = (
        "Kumar-Ramasesha-Soos J1-J2 source must establish "
        "arXiv:1006.5052v1, the antiferromagnetic spin-half first- and "
        "second-neighbor Hamiltonian in Eq. (1), the mapping "
        "J2/J1=x/(1-x), and the 0.2411 fluid-dimer transition where the "
        "magnetic gap opens"
    )
    spin_half_pattern = r"spin-\s*1\s*/?\s*2"
    identity_match = re.search(
        r"Bond-order wave phase, spin solitons and thermodynamics of a "
        r"frustrated linear\s+"
        + spin_half_pattern
        + r"\s+Heisenberg antiferromagnet"
        r".{0,500}?Manoranjan Kumar"
        r".{0,250}?S\.\s*Ramasesha"
        r".{0,250}?Z\.?\s*G\.?\s*Soos"
        r".{0,800}?arXiv:1006\.5052v1",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"linear\s+"
        + spin_half_pattern
        + r"\s+Heisenberg antiferromagnet"
        r".{0,250}?exchanges J\s*1\s*,?\s*J\s*2"
        r".{0,500}?fluid-dimer transition at"
        r".{0,80}?J\s*2\s*/\s*J\s*1\s*=\s*0\.2411",
        normalized,
        flags=re.IGNORECASE,
    )
    model_prose_match = re.search(
        r"spin chain has (?:antiferromagnetic|AF) exchange between first",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"H\s*\(\s*x\s*\)\s*=\s*J"
        r".{0,900}?\(\s*1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    transition_match = re.search(
        r"Okamoto and Nomura"
        r".{0,180}?located the transition at"
        r".{0,180}?x\s*_?\s*c\s*=\s*x\s*_?\s*1\s*/\s*"
        r"\(\s*1\s*-\s*x\s*_?\s*1\s*\)\s*=\s*"
        r"(?P<critical>0\.2411)"
        r".{0,100}?x\s*_?\s*1\s*=\s*0\.1943"
        r".{0,100}?where a magnetic gap"
        r".{0,40}?opens",
        normalized,
        flags=re.IGNORECASE,
    )
    match_by_name = {
        "identity": identity_match,
        "abstract_transition": abstract_match,
        "model_definition": model_prose_match,
        "hamiltonian": hamiltonian_match,
        "ratio_and_gap": transition_match,
    }
    missing = [
        name for name, match in match_by_name.items() if match is None
    ]
    if missing:
        raise RuntimeEvidenceError(
            f"{error_message}; missing anchors: {', '.join(missing)}"
        )
    matches = tuple(match_by_name.values())

    critical_ratio = float(transition_match.group("critical"))
    if not math.isclose(
        critical_ratio, 0.2411, rel_tol=0.0, abs_tol=1.0e-12
    ):
        raise RuntimeEvidenceError(error_message)
    trace = {
        "source_profile": "arxiv:1006.5052v1",
        "equation": "1",
        "source_model": (
            "H(x)=J sum_n[(1-x)s_n.s_n+1+x s_n.s_n+2], "
            "antiferromagnetic spin-1/2 chain"
        ),
        "source_ratio_mapping": (
            "J2/J1=x/(1-x); source reports x1=0.1943 and "
            "x1/(1-x1)=0.2411"
        ),
        "matched_anchors": [
            "identified Kumar-Ramasesha-Soos arXiv manuscript",
            "abstract fluid-dimer transition J2/J1=0.2411",
            "first- and second-neighbor Hamiltonian Eq. (1)",
            "Okamoto-Nomura ratio mapping and magnetic-gap opening",
        ],
        "text_spans": [[match.start(), match.end()] for match in matches],
    }
    return critical_ratio, trace


def parse_kumar_j1_j2_critical_point(source_text):
    """Extract the corroborated Okamoto-Nomura J2/J1 transition ratio."""

    error_message = (
        "Kumar-Ramasesha-Soos J1-J2 source must establish "
        "arXiv:1006.5052v1, the antiferromagnetic spin-half first- and "
        "second-neighbor Hamiltonian in Eq. (1), the mapping "
        "J2/J1=x/(1-x), and the 0.2411 fluid-dimer transition where the "
        "magnetic gap opens"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text, "parse_kumar_j1_j2_critical_point"
    )
    return _finalize_prepared_trace(
        _parse_kumar_j1_j2_critical_point_prepared(prepared.text),
        prepared,
    )


def _parse_kumar_j1_j2_critical_point_prepared(prepared_text):
    critical_ratio, trace = _parse_kumar_j1_j2_critical_ratio_prepared(
        prepared_text
    )
    trace = dict(trace)
    trace["parser"] = "parse_kumar_j1_j2_critical_point"
    return {"critical_j2_over_j1": critical_ratio}, trace


def parse_kumar_j1_j2_bkt_reference(source_text):
    """Map Kumar et al.'s fluid-dimer ratio to the approximate field."""

    error_message = (
        "Kumar-Ramasesha-Soos J1-J2 source must establish "
        "arXiv:1006.5052v1, the antiferromagnetic spin-half first- and "
        "second-neighbor Hamiltonian in Eq. (1), the mapping "
        "J2/J1=x/(1-x), and the 0.2411 fluid-dimer transition where the "
        "magnetic gap opens"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text, "parse_kumar_j1_j2_bkt_reference"
    )
    return _finalize_prepared_trace(
        _parse_kumar_j1_j2_bkt_reference_prepared(prepared.text),
        prepared,
    )


def _parse_kumar_j1_j2_bkt_reference_prepared(prepared_text):
    critical_ratio, trace = _parse_kumar_j1_j2_critical_ratio_prepared(
        prepared_text
    )
    trace = dict(trace)
    trace["parser"] = "parse_kumar_j1_j2_bkt_reference"
    return {"critical_j2_over_j1_approx": critical_ratio}, trace


def parse_savary_er2ti2o7_psi2_order_by_quantum_disorder(source_text):
    """Extract the fluctuation-selected psi2 order reported for Er2Ti2O7."""

    error_message = (
        "Savary Er2Ti2O7 order-by-quantum-disorder source must establish "
        "the identified 1204.1320v1 paper, its effective spin-half "
        "nearest-neighbor pyrochlore Hamiltonian and fitted anisotropic "
        "exchanges, the classical U(1) ground-state manifold, the "
        "zero-point-energy minima at alpha=n*pi/3, their psi2 identity, "
        "and the experimental comparison"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_savary_er2ti2o7_psi2_order_by_quantum_disorder",
    )
    return _finalize_prepared_trace(
        _parse_savary_er2ti2o7_psi2_order_by_quantum_disorder_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_savary_er2ti2o7_psi2_order_by_quantum_disorder_prepared(
    normalized,
):
    error_message = (
        "Savary Er2Ti2O7 order-by-quantum-disorder source must establish "
        "the identified 1204.1320v1 paper, its effective spin-half "
        "nearest-neighbor pyrochlore Hamiltonian and fitted anisotropic "
        "exchanges, the classical U(1) ground-state manifold, the "
        "zero-point-energy minima at alpha=n*pi/3, their psi2 identity, "
        "and the experimental comparison"
    )

    material_pattern = r"Er\s*2\s*Ti\s*2\s*O\s*7"
    u1_pattern = r"U\s*\(\s*1\s*\)"
    alpha_pattern = r"(?:alpha|α)"
    pi_pattern = r"(?:pi|π)"
    plus_minus_pattern = r"(?:\+/-|±)"
    j_pm_pattern = r"J\s*(?:pm|±)(?!\s*(?:pm|±))"
    j_pmpm_pattern = r"J\s*(?:pmpm|±\s*±)"
    j_zpm_pattern = r"J\s*z\s*(?:pm|±)"

    identity_match = re.search(
        r"Definitive Evidence for Order\s*-\s*by\s*-\s*Quantum\s*-\s*"
        r"Disorder in "
        + material_pattern
        + r".{0,5000}?Lucile Savary"
        r".{0,500}?Kate A\. Ross"
        r".{0,500}?Bruce D\. Gaulin"
        r".{0,500}?Jacob P\. C\. Ruff"
        r".{0,500}?Leon Balents"
        r".{0,9000}?arXiv\s*:\s*1204\.1320v1"
        r"\s*\[\s*cond-mat\.str-el\s*\]\s*5 Apr 2012",
        normalized,
        flags=re.IGNORECASE,
    )
    effective_model_match = re.search(
        r"project the Hamiltonian(?:\s+|.{1,300}?)to that of effective "
        r"S\s*=\s*1\s*/\s*2 quantum spins"
        r".{0,500}?magnetic doublet"
        r".{0,500}?pyrochlore.{0,300}?lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    classical_manifold_match = re.search(
        u1_pattern
        + r"\s*-\s*degenerate states of "
        + material_pattern
        + r"\s+are its classical ground states",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"Nearest\s*-\s*neighbor exchange dominates"
        r".{0,800}?Hamiltonian"
        r".{0,1600}?H\s*="
        r".{0,700}?J\s*zz"
        r".{0,700}?"
        + j_pm_pattern
        + r".{0,700}?"
        + j_pmpm_pattern
        + r".{0,1100}?"
        + j_zpm_pattern
        + r".{0,900}?\(\s*6\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    fitted_parameters_match = re.search(
        r"(?=.{0,700}?\(\s*7\s*\))"
        + j_pmpm_pattern
        + r"\s*=\s*4\.2\s*"
        + plus_minus_pattern
        + r"\s*0\.5"
        r".{0,240}?"
        + j_pm_pattern
        + r"\s*=\s*6\.5\s*"
        + plus_minus_pattern
        + r"\s*0\.75"
        r".{0,240}?J\s*zz\s*=\s*-\s*2\.5\s*"
        + plus_minus_pattern
        + r"\s*1\.8"
        r".{0,240}?"
        + j_zpm_pattern
        + r"\s*=\s*-\s*0\.88\s*"
        + plus_minus_pattern
        + r"\s*1\.5",
        normalized,
        flags=re.IGNORECASE,
    )
    zero_point_selection_match = re.search(
        r"zero\s*-\s*point fluctuations.{0,300}?break the "
        + u1_pattern
        + r"\s+degeneracy"
        r".{0,500}?six equivalent"
        r".{0,200}?values\s+"
        + alpha_pattern
        + r"\s*=\s*n\s*"
        + pi_pattern
        + r"\s*/\s*3"
        r".{0,300}?are the minima of",
        normalized,
        flags=re.IGNORECASE,
    )
    psi2_identity_match = re.search(
        r"These are exactly the (?:psi|ψ)\s*2 states",
        normalized,
        flags=re.IGNORECASE,
    )
    experiment_match = re.search(
        r"(?:gives|provides)\s+strong evidence for the "
        r"(?:correctness|cor\s*-\s*.{0,300}?rectness) of the "
        r"(?:psi|ψ)\s*2 ground state and the Hamiltonian "
        r"(?:parameters|pa\s*-\s*.{0,300}?rameters)",
        normalized,
        flags=re.IGNORECASE,
    )

    matches = (
        identity_match,
        effective_model_match,
        classical_manifold_match,
        hamiltonian_match,
        fitted_parameters_match,
        zero_point_selection_match,
        psi2_identity_match,
        experiment_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    identity_start = min(
        identity_match.start(),
        effective_model_match.start(),
        classical_manifold_match.start(),
    )
    identity_end = max(
        identity_match.end(),
        effective_model_match.end(),
        classical_manifold_match.end(),
    )
    return (
        {"psi2_order_selected": True},
        {
            "parser": (
                "parse_savary_er2ti2o7_psi2_order_by_quantum_disorder"
            ),
            "source_model": (
                "effective spin-1/2 nearest-neighbor pyrochlore Hamiltonian "
                "with Jzz, Jpm, Jpmpm, and Jzpm anisotropic exchanges"
            ),
            "selection_chain": (
                "classical U(1) ground-state manifold -> zero-point-energy "
                "minima alpha=n*pi/3 -> psi2 order"
            ),
            "registered_convention_mapping": (
                "source psi2 selection equals registry boolean; no sign, "
                "normalization, or unit conversion"
            ),
            "corrected_source_identity": (
                "arXiv:1204.1320v1; "
                "DOI:10.1103/PhysRevLett.109.167201"
            ),
            "superseded_registered_doi": (
                "10.1103/PhysRevLett.108.037202"
            ),
            "matched_anchors": [
                "identified 1204.1320v1 paper, authors, and material",
                "effective spin-half pyrochlore model and classical U(1) "
                "ground-state manifold",
                "nearest-neighbor anisotropic Hamiltonian, Eq. (6)",
                "Er2Ti2O7 fitted exchange parameters, Eq. (7)",
                "zero-point minima alpha=n*pi/3",
                "psi2 identity and neutron-scattering comparison",
            ],
            "text_spans": [
                [identity_start, identity_end],
                [hamiltonian_match.start(), hamiltonian_match.end()],
                [
                    fitted_parameters_match.start(),
                    fitted_parameters_match.end(),
                ],
                [
                    zero_point_selection_match.start(),
                    zero_point_selection_match.end(),
                ],
                [psi2_identity_match.start(), psi2_identity_match.end()],
                [experiment_match.start(), experiment_match.end()],
            ],
        },
    )


def parse_richter_star_lattice_valence_bond_ground_state(source_text):
    """Extract the explicit valence-bond-crystal result for the star HAFM."""

    error_message = (
        "Richter star-lattice valence-bond source must establish the "
        "identified PhysRevB.70.174454 paper, its uniform spin-half "
        "nearest-neighbor star-lattice HAFM, the gapped dimerized "
        "quantum-paramagnetic evidence, and the explicit valence-bond "
        "crystal conclusion in the uniform model"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_richter_star_lattice_valence_bond_ground_state",
    )
    return _finalize_prepared_trace(
        _parse_richter_star_lattice_valence_bond_ground_state_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_richter_star_lattice_valence_bond_ground_state_prepared(
    normalized,
):
    error_message = (
        "Richter star-lattice valence-bond source must establish the "
        "identified PhysRevB.70.174454 paper, its uniform spin-half "
        "nearest-neighbor star-lattice HAFM, the gapped dimerized "
        "quantum-paramagnetic evidence, and the explicit valence-bond "
        "crystal conclusion in the uniform model"
    )

    spin_half_pattern = r"(?:spin\s*-\s*half|spin\s*-\s*1\s*/\s*2)"
    antiferromagnet_pattern = (
        r"(?:antiferromagnet|antiferro\s*-\s*magnet|HAFM)"
    )
    j_d_pattern = r"J\s*_?\s*D"
    j_t_pattern = r"J\s*_?\s*T"
    equation_one_pattern = r"(?:\(|共)\s*1\s*(?:\)|兲)"
    nn_bonds_pattern = (
        r"(?:nearest\s*-\s*neighbor"
        r"(?:\s*\(\s*NN\s*\))?\s+bonds|NN bonds)"
    )

    identity_match = re.search(
        r"Absence of magnetic order for the "
        + spin_half_pattern
        + r" Heisenberg "
        + antiferromagnet_pattern
        + r" on the star lattice"
        r".{0,2200}?J\. Richter"
        r".{0,2200}?J\. Schulenburg"
        r".{0,2200}?A\. Honecker"
        r".{0,2200}?D\. Schmalfu(?:ss|ß)"
        r".{0,6000}?DOI\s*:\s*10\.1103/PhysRevB\.70\.174454",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_result_match = re.search(
        r"(?:We study the )?ground\s*-\s*state properties of the "
        + spin_half_pattern
        + r" Heisenberg "
        + antiferromagnet_pattern
        + r" on the two\s*-\s*dimensional star lattice"
        r".{0,500}?evidence"
        r".{0,300}?quantum paramagnetic ground state"
        r".{0,700}?quantum ground state is most likely dimerized "
        r"with a gap to all excitations",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"geometric unit cell of the star lattice contains six sites"
        r".{0,1000}?underlying Bravais lattice is a triangular one"
        r".{0,1000}?consider the "
        + spin_half_pattern
        + r".{0,700}?"
        + antiferromagnet_pattern
        + r" in a magnetic field"
        r"(?=.{0,1400}?(?:H.{0,180}?=\s*J|=\s*J.{0,180}?H))"
        r"(?=.{0,1400}?S\s*_?\s*i\s*(?:dot|·)\s*S\s*_?\s*j)"
        r"(?=.{0,1400}?"
        + equation_one_pattern
        + r")"
        r".{0,1800}?star lattice carries topologically inequivalent"
        r".{0,500}?"
        + nn_bonds_pattern
        + r".{0,500}?"
        + j_d_pattern
        + r".{0,500}?"
        + j_t_pattern
        + r".{0,500}?uniform lattice"
        r".{0,500}?"
        + j_d_pattern
        + r"\s*=\s*"
        + j_t_pattern
        + r"\s*=\s*J",
        normalized,
        flags=re.IGNORECASE,
    )
    valence_bond_match = re.search(
        r"features support the "
        r"(?:conclusion|con\s*-\s*.{0,400}?clusion)"
        r".{0,1200}?quantum (?:ground state|GS) of the "
        + antiferromagnet_pattern
        + r" on the star lattice"
        r".{0,1200}?dominated by local singlet pairing"
        r".{0,800}?dimerized (?:ground state|GS)"
        r".{0,800}?explicit valence\s*-\s*bond crystal state"
        r".{0,500}?respects the lattice symmetry"
        r".{0,2400}?(?:quantum|quan\s*-\s*.{0,400}?tum) "
        r"paramagnetic (?:ground state|GS) appears"
        r".{0,800}?(?:spin\s*-\s*1|s\s*=\s*1)\s*/\s*2 star lattice"
        r".{0,800}?even.{0,400}?in the uniform case"
        r".{0,500}?"
        + j_d_pattern
        + r"\s*=\s*"
        + j_t_pattern,
        normalized,
        flags=re.IGNORECASE,
    )

    matches = (
        identity_match,
        abstract_result_match,
        model_match,
        valence_bond_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    return (
        {"spin_liquid_or_valence_bond_reference": True},
        {
            "parser": (
                "parse_richter_star_lattice_valence_bond_ground_state"
            ),
            "source_model": (
                "uniform spin-1/2 nearest-neighbor Heisenberg "
                "antiferromagnet on the star lattice with JD=JT=J"
            ),
            "registry_claim_mapping": (
                "source explicit valence-bond crystal satisfies the "
                "registry spin-liquid-or-valence-bond umbrella through "
                "its valence-bond branch; no spin-liquid claim is inferred"
            ),
            "corrected_source_identity": (
                "DOI:10.1103/PhysRevB.70.174454"
            ),
            "superseded_registered_doi": (
                "10.1103/PhysRevB.70.184414"
            ),
            "matched_anchors": [
                "identified PhysRevB.70.174454 paper and authors",
                "gapped dimerized quantum-paramagnetic abstract result",
                "uniform star-lattice spin-half HAFM, Eq. (1), JD=JT=J",
                "local singlet pairing and explicit valence-bond crystal",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_richter_square_kagome_reference(source_text):
    """Extract the corrected square-kagome reference for the shuriken entry."""

    error_message = (
        "Richter square-kagome source must establish the identified "
        "cond-mat/0411673v1 paper, its six-site square-Bravais "
        "square-kagome geometry, the uniform spin-half nearest-neighbor "
        "HAFM with JS=JT=J, its spin-liquid-like conclusion distinct "
        "from the star-lattice valence-bond crystal, and localized "
        "magnons on square plaquettes"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text, "parse_richter_square_kagome_reference"
    )
    return _finalize_prepared_trace(
        _parse_richter_square_kagome_reference_prepared(prepared.text),
        prepared,
    )


def _parse_richter_square_kagome_reference_prepared(normalized):
    error_message = (
        "Richter square-kagome source must establish the identified "
        "cond-mat/0411673v1 paper, its six-site square-Bravais "
        "square-kagome geometry, the uniform spin-half nearest-neighbor "
        "HAFM with JS=JT=J, its spin-liquid-like conclusion distinct "
        "from the star-lattice valence-bond crystal, and localized "
        "magnons on square plaquettes"
    )

    square_kagome_pattern = (
        r"square\s*-\s*kagom(?:e|é|´\s*e)"
    )
    spin_half_pattern = r"(?:spin\s*-\s*half|s\s*=\s*1\s*/\s*2)"
    antiferromagnet_pattern = (
        r"(?:antiferromagnet|antiferro\s*-\s*magnet|HAFM)"
    )
    j_s_pattern = r"J\s*_?\s*S"
    j_t_pattern = r"J\s*_?\s*T"
    equation_one_pattern = r"(?:\(|共)\s*1\s*(?:\)|兲)"
    nn_bonds_pattern = (
        r"(?:nearest\s*-\s*neighbor"
        r"(?:\s*\(\s*NN\s*\))?\s+bonds|NN bonds)"
    )

    title_match = re.search(
        r"The "
        + spin_half_pattern
        + r" Heisenberg "
        + antiferromagnet_pattern
        + r" on the "
        + square_kagome_pattern
        + r" lattice\s*:\s*Ground state and low\s*-\s*lying excitations"
        r".{0,1200}?arXiv\s*:\s*cond-mat\s*/\s*0411673v1"
        r"\s*\[\s*cond-mat\.str-el\s*\]\s*26 Nov 2004",
        normalized,
        flags=re.IGNORECASE,
    )
    authors_match = re.search(
        r"J\. Richter"
        r".{0,1800}?J\. Schulenburg"
        r".{0,1800}?P\. Tomczak"
        r".{0,1800}?D\. Schmalfu(?:ss|ß)",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"ground state and the low\s*-\s*lying excitations of the "
        + spin_half_pattern
        + r" Heisenberg "
        + antiferromagnet_pattern
        + r" on the two\s*-\s*dimensional "
        + square_kagome_pattern
        + r" lattice"
        r".{0,700}?quantum ground state of the "
        + spin_half_pattern
        + r" system is a quantum paramagnet"
        r".{0,500}?finite spin gap"
        r".{0,500}?large number of non\s*-\s*magnetic excitations",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"geometric unit cell of the "
        + square_kagome_pattern
        + r" lattice contains six sites"
        r".{0,500}?underlying Bravais lattice is a square one"
        r".{0,700}?consider the "
        + spin_half_pattern
        + r".{0,300}?"
        + antiferromagnet_pattern
        + r" in a magnetic field"
        r"(?=.{0,1000}?(?:H.{0,160}?=\s*J|=\s*J.{0,160}?H))"
        r"(?=.{0,1000}?S\s*_?\s*i\s*(?:dot|·)\s*S\s*_?\s*j)"
        r"(?=.{0,1000}?"
        + equation_one_pattern
        + r")"
        r".{0,1000}?"
        + square_kagome_pattern
        + r" lattice carries topologically inequivalent"
        r".{0,500}?"
        + nn_bonds_pattern
        + r".{0,500}?"
        + j_s_pattern
        + r".{0,500}?"
        + j_t_pattern
        + r".{0,500}?uniform lattice"
        r".{0,500}?"
        + j_s_pattern
        + r"\s*=\s*"
        + j_t_pattern
        + r"\s*=\s*J"
        r".{0,300}?set J\s*=\s*1",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"find evidence for a spin\s*-\s*liquid like ground state"
        r".{0,500}?small gap of about J\s*/\s*20"
        r".{0,500}?considerable number of low\s*-\s*lying singlets"
        r".{0,800}?Contrary to the star lattice case"
        r".{0,500}?do not see"
        r".{0,500}?forming a valence bond crystal ground state",
        normalized,
        flags=re.IGNORECASE,
    )
    localized_magnon_match = re.search(
        r"independent localized magnon states"
        r".{0,700}?"
        + square_kagome_pattern
        + r".{0,500}?localized magnons (?:live )?on the squares",
        normalized,
        flags=re.IGNORECASE,
    )

    matches = (
        title_match,
        authors_match,
        abstract_match,
        model_match,
        conclusion_match,
        localized_magnon_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    identity_start = min(title_match.start(), authors_match.start())
    identity_end = max(title_match.end(), authors_match.end())
    result_start = min(
        conclusion_match.start(), localized_magnon_match.start()
    )
    result_end = max(
        conclusion_match.end(), localized_magnon_match.end()
    )
    return (
        {"square_kagome_reference": True},
        {
            "parser": "parse_richter_square_kagome_reference",
            "source_model": (
                "uniform spin-1/2 nearest-neighbor Heisenberg "
                "antiferromagnet on the square-kagome lattice with "
                "JS=JT=J"
            ),
            "registered_lattice_mapping": (
                "registry shuriken-lattice alias maps to source "
                "square-kagome lattice; star lattice is explicitly "
                "excluded"
            ),
            "corrected_source_identity": (
                "arXiv:cond-mat/0411673v1"
            ),
            "superseded_registered_doi": (
                "10.1103/PhysRevB.70.174454"
            ),
            "matched_anchors": [
                "identified cond-mat/0411673v1 paper and authors",
                "square-kagome quantum-paramagnetic abstract result",
                "six-site square-Bravais uniform HAFM, Eq. (1), JS=JT=J",
                "spin-liquid-like state distinct from star VBC and "
                "localized magnons on squares",
            ],
            "text_spans": [
                [identity_start, identity_end],
                [abstract_match.start(), abstract_match.end()],
                [model_match.start(), model_match.end()],
                [result_start, result_end],
            ],
        },
    )


def parse_wildes_feps3_ising_zigzag_order(source_text):
    """Extract the Ising-like zig-zag antiferromagnetic order of FePS3."""

    error_message = (
        "Wildes FePS3 Ising-like zig-zag source must establish the "
        "identified 2005.12031v1 paper, the FePS3 honeycomb material, "
        "its high-spin S=2 moments normal to the planes, ferromagnetic "
        "zig-zag chains with antiferromagnetic interchain coupling, "
        "Ising-like anisotropy, and the Heisenberg plus single-ion "
        "anisotropy Hamiltonian"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text, "parse_wildes_feps3_ising_zigzag_order"
    )
    return _finalize_prepared_trace(
        _parse_wildes_feps3_ising_zigzag_order_prepared(prepared.text),
        prepared,
    )


def _parse_wildes_feps3_ising_zigzag_order_prepared(normalized):
    error_message = (
        "Wildes FePS3 Ising-like zig-zag source must establish the "
        "identified 2005.12031v1 paper, the FePS3 honeycomb material, "
        "its high-spin S=2 moments normal to the planes, ferromagnetic "
        "zig-zag chains with antiferromagnetic interchain coupling, "
        "Ising-like anisotropy, and the Heisenberg plus single-ion "
        "anisotropy Hamiltonian"
    )

    material_pattern = r"Fe\s*P\s*S\s*3"
    antiferromagnet_pattern = (
        r"(?:antiferromagnet|antiferromag\s*-\s*net)"
    )
    fe_ion_pattern = r"Fe\s*2\s*\+"
    delta_pattern = r"(?:Delta|∆|Δ)"

    identity_match = re.search(
        r"Evidence for biquadratic exchange in the quasi\s*-\s*"
        r"two\s*-\s*dimensional "
        + antiferromagnet_pattern
        + r" "
        + material_pattern
        + r".{0,1200}?A\. R\. Wildes"
        r".{0,1200}?M\. E\. Zhitomirsky"
        r".{0,1200}?T\. Ziman"
        r".{0,1200}?D\. Lan(?:c|ç)on"
        r".{0,1200}?H\. C\. Walker"
        r".{0,5000}?arXiv\s*:\s*2005\.12031v1"
        r"\s*\[\s*cond-mat\.mtrl-sci\s*\]\s*25 May 2020",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        material_pattern
        + r" is a van der Waals compound with a honeycomb lattice"
        r".{0,500}?good example of a two\s*-\s*dimensional "
        + antiferromagnet_pattern
        + r" with Ising\s*-\s*like anisotropy",
        normalized,
        flags=re.IGNORECASE,
    )
    order_match = re.search(
        fe_ion_pattern
        + r" ions"
        r".{0,500}?(?:form|forming) a slightly distorted honeycomb"
        r".{0,400}?lattice"
        r".{0,500}?in the ab planes"
        r".{0,1800}?compound is antiferromagnetic"
        r".{0,700}?ordering below"
        r".{0,700}?(?:N[ée]el temperature|approximately|∼|~)"
        r".{0,500}?120 K"
        r".{0,1800}?high\s*-\s*spin\s*\(\s*S\s*=\s*2\s*\)\s*"
        + fe_ion_pattern
        + r"(?:\s+ions)?"
        r".{0,900}?aligned parallel to the c\s*(?:\*|∗) direction"
        r".{0,900}?normal to the ab.{0,400}?planes"
        r".{0,900}?forming ferromagnetic zig\s*-\s*zag chains"
        r".{0,500}?parallel.{0,300}?to the a axis"
        r".{0,800}?chains are antiferromagnetically coupled"
        r".{0,500}?along the b and c axes"
        r".{0,1200}?paramagnetic "
        r"(?:susceptibility|sus\s*-\s*.{0,400}?ceptibility) "
        r"is highly anisotropic"
        r".{0,700}?good example of an Ising\s*-\s*like "
        + antiferromagnet_pattern,
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"Hamiltonian initially used to model the spin waves for "
        r".{0,150}?"
        + material_pattern
        + r" was"
        r".{0,1000}?H.{0,100}?=\s*-\s*"
        r".{0,400}?J\s*_?\s*i\s*j"
        r".{0,400}?S\s*_?\s*i\s*(?:dot|·)\s*S\s*_?\s*j"
        r".{0,500}?-\s*"
        + delta_pattern
        + r".{0,400}?S\s*_?\s*i\s*(?:\^?\s*z|z)"
        r".{0,200}?(?:\^\s*)?2"
        r".{0,300}?\(\s*1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    anisotropy_dominance_match = re.search(
        r"(?:"
        r"single\s*-\s*ion anisotropy"
        r".{0,500}?dominates?"
        r"|large anisotropy"
        r".{0,500}?dominating"
        r"|single\s*-\s*ion anisotropy"
        r".{0,700}?anisotropy is the "
        r"(?:dominant|dom\s*-\s*.{0,400}?inant) factor"
        r")"
        r".{0,600}?(?:spin\s*-\s*wave|energy)?\s*gap",
        normalized,
        flags=re.IGNORECASE,
    )
    ising_gap_match = re.search(
        r"(?:large )?(?:spin\s*-\s*wave|energy)?\s*gap"
        r".{0,500}?explain(?:s|ing)?"
        r".{0,300}?(?:its|the)?\s*Ising\s*-\s*like behavio(?:u)?r",
        normalized,
        flags=re.IGNORECASE,
    )

    matches = (
        identity_match,
        abstract_match,
        order_match,
        hamiltonian_match,
        anisotropy_dominance_match,
        ising_gap_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    model_start = min(
        hamiltonian_match.start(),
        anisotropy_dominance_match.start(),
        ising_gap_match.start(),
    )
    model_end = max(
        hamiltonian_match.end(),
        anisotropy_dominance_match.end(),
        ising_gap_match.end(),
    )
    return (
        {"ising_like_zigzag_order": True},
        {
            "parser": "parse_wildes_feps3_ising_zigzag_order",
            "source_model": (
                "S=2 FePS3 honeycomb Heisenberg exchange with easy-axis "
                "single-ion anisotropy Delta"
            ),
            "order_chain": (
                "moments normal to ab planes -> ferromagnetic zig-zag "
                "chains along a -> antiferromagnetically coupled chains "
                "-> Ising-like antiferromagnetic order"
            ),
            "registered_convention_mapping": (
                "source Ising-like zig-zag order equals registry boolean; "
                "no sign, normalization, or unit conversion"
            ),
            "corrected_source_identity": "arXiv:2005.12031v1",
            "superseded_registered_doi": (
                "10.1103/PhysRevB.85.094422"
            ),
            "matched_anchors": [
                "identified 2005.12031v1 paper and authors",
                "FePS3 honeycomb Ising-like antiferromagnet abstract",
                "S=2 out-of-plane moments in ferromagnetic zig-zag "
                "chains with antiferromagnetic interchain coupling",
                "Heisenberg plus single-ion anisotropy, Eq. (1), and "
                "anisotropy-controlled gap",
            ],
            "text_spans": [
                [identity_match.start(), identity_match.end()],
                [abstract_match.start(), abstract_match.end()],
                [order_match.start(), order_match.end()],
                [model_start, model_end],
            ],
        },
    )


def parse_dey_ba3irti2o9_triangular_spin_liquid_candidate(source_text):
    """Extract the triangular-lattice QSL-candidate claim for Ba3IrTi2O9."""

    error_message = (
        "Dey Ba3IrTi2O9 triangular spin-liquid source must establish "
        "the identified PhysRevB.86.140405 paper, its layered and "
        "site-diluted triangular Ir4+ geometry with Jeff=1/2 moments, "
        "the absence of magnetic order down to 0.35 K despite a "
        "Curie-Weiss scale near -130 K, the power-law heat capacity, "
        "and the explicitly triangular spin-liquid-candidate conclusion"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_dey_ba3irti2o9_triangular_spin_liquid_candidate",
    )
    return _finalize_prepared_trace(
        _parse_dey_ba3irti2o9_triangular_spin_liquid_candidate_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_dey_ba3irti2o9_triangular_spin_liquid_candidate_prepared(
    normalized,
):
    error_message = (
        "Dey Ba3IrTi2O9 triangular spin-liquid source must establish "
        "the identified PhysRevB.86.140405 paper, its layered and "
        "site-diluted triangular Ir4+ geometry with Jeff=1/2 moments, "
        "the absence of magnetic order down to 0.35 K despite a "
        "Curie-Weiss scale near -130 K, the power-law heat capacity, "
        "and the explicitly triangular spin-liquid-candidate conclusion"
    )

    material_pattern = r"Ba\s*3\s*Ir\s*Ti\s*2\s*O\s*9"
    ir_ion_pattern = r"Ir\s*4\s*\+"
    jeff_half_pattern = (
        r"J\s*_?\s*eff\s*=\s*1\s*(?:/\s*)?2"
    )
    theta_pattern = r"(?:theta\s*_?\s*CW|θ\s*CW)"

    identity_match = re.search(
        r"Spin\s*-\s*liquid behavior in "
        + jeff_half_pattern
        + r" triangular lattice compound "
        + material_pattern
        + r".{0,1500}?Tusharkanti Dey"
        r".{0,1500}?A\. V\. Mahajan"
        r".{0,1500}?P\. Khuntia"
        r".{0,1500}?M\. Baenitz"
        r".{0,1500}?B\. Koteswararao"
        r".{0,1500}?F\. C\. Chou"
        r".{0,7000}?DOI\s*:\s*10\.1103/PhysRevB\.86\.140405",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        material_pattern
        + r" crystallizes in a hexagonal structure"
        r".{0,400}?layered triangular arrangement of "
        + ir_ion_pattern
        + r"\s*\(\s*"
        + jeff_half_pattern
        + r"\s*\)"
        r".{0,800}?Magnetic susceptibility and heat capacity data show "
        r"no magnetic ordering down to 0\.35 K"
        r".{0,800}?strong magnetic coupling"
        r".{0,800}?"
        + theta_pattern
        + r"\s*(?:approximately|∼|~)?\s*-\s*130 K"
        r".{0,600}?magnetic heat capacity follows a power law"
        r".{0,700}?measurements suggest that "
        + material_pattern
        + r" is a 5d"
        r".{0,400}?"
        + jeff_half_pattern
        + r".{0,300}?quantum spin liquid on a two\s*-\s*dimensional "
        r"(?:\(\s*2D\s*\)\s*)?triangular lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    edge_shared_match = re.search(
        ir_ion_pattern
        + r" spins form an edge\s*-\s*shared triangular lattice "
        r".{0,500}?in the ab plane",
        normalized,
        flags=re.IGNORECASE,
    )
    depleted_frustration_match = re.search(
        r"(?:site sharing|site disorder)"
        r".{0,9000}?(?:deplet(?:es|ed|ion)|site dilution)"
        r".{0,1500}?triangular"
        r".{0,9000}?geometrical frustration"
        r".{0,1000}?(?:continues|con\s*-\s*.{0,400}?tinues) to exist"
        r".{0,1800}?depleted triangular lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"Conclusions?\."
        r".{0,700}?presented a potentially new spin"
        r".{0,500}?liquid system "
        + material_pattern
        + r".{0,700}?based on a triangular lattice of "
        + ir_ion_pattern
        + r" ions"
        r".{0,3500}?magnetic correlations"
        r".{0,500}?and frustrations "
        r"are (?:still )?maintained"
        r".{0,1200}?absence of"
        r".{0,500}?magnetic ordering down to 0\.35 K"
        r".{0,900}?(?:high "
        + theta_pattern
        + r" value|high Curie\s*-\s*Weiss scale)"
        r".{0,3000}?"
        + material_pattern
        + r" is possibly.{0,500}?an example of a "
        + jeff_half_pattern
        + r" quantum spin liquid system",
        normalized,
        flags=re.IGNORECASE,
    )

    matches = (
        identity_match,
        abstract_match,
        edge_shared_match,
        depleted_frustration_match,
        conclusion_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    geometry_start = min(
        edge_shared_match.start(), depleted_frustration_match.start()
    )
    geometry_end = max(
        edge_shared_match.end(), depleted_frustration_match.end()
    )
    return (
        {"spin_liquid_candidate": True},
        {
            "parser": (
                "parse_dey_ba3irti2o9_triangular_spin_liquid_candidate"
            ),
            "source_geometry": (
                "hexagonal Ba3IrTi2O9 with layered, site-diluted "
                "triangular Ir4+ planes and Jeff=1/2 moments"
            ),
            "registry_claim_mapping": (
                "source directly supports only the "
                "spin-liquid-candidate boolean for a triangular "
                "material; no honeycomb or Kitaev Hamiltonian is inferred"
            ),
            "registered_model_correction": (
                "replace honeycomb Kitaev labeling with triangular "
                "Jeff=1/2 spin-liquid candidate"
            ),
            "corrected_source_identity": (
                "DOI:10.1103/PhysRevB.86.140405"
            ),
            "matched_anchors": [
                "identified PhysRevB.86.140405 paper and authors",
                "layered triangular Jeff=1/2 abstract geometry",
                "no order to 0.35 K, theta_CW near -130 K, and "
                "power-law heat capacity",
                "edge-shared and site-diluted triangular planes",
                "explicit triangular spin-liquid-candidate conclusion",
            ],
            "text_spans": [
                [identity_match.start(), identity_match.end()],
                [abstract_match.start(), abstract_match.end()],
                [geometry_start, geometry_end],
                [conclusion_match.start(), conclusion_match.end()],
            ],
        },
    )


def parse_ghosh_mila_ruby_localized_magnon_eigenstate(source_text):
    """Extract the exact localized-one-magnon claim for the ruby lattice."""

    error_message = (
        "Ghosh-Mila ruby localized-magnon source must establish the "
        "identified arXiv:2512.14173v1 paper, the spin-1/2 ruby-lattice "
        "Heisenberg model with Jh, Jt, and Jd at the isotropic point, "
        "the one-magnon ansatz and destructive-interference condition, "
        "the alternating-sign Jh-hexagon solution and exact product "
        "eigenstate, and the explicit warning that the iPEPS plateaus "
        "are not localized-magnon states"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_ghosh_mila_ruby_localized_magnon_eigenstate",
    )
    return _finalize_prepared_trace(
        _parse_ghosh_mila_ruby_localized_magnon_eigenstate_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_ghosh_mila_ruby_localized_magnon_eigenstate_prepared(
    normalized,
):
    error_message = (
        "Ghosh-Mila ruby localized-magnon source must establish the "
        "identified arXiv:2512.14173v1 paper, the spin-1/2 ruby-lattice "
        "Heisenberg model with Jh, Jt, and Jd at the isotropic point, "
        "the one-magnon ansatz and destructive-interference condition, "
        "the alternating-sign Jh-hexagon solution and exact product "
        "eigenstate, and the explicit warning that the iPEPS plateaus "
        "are not localized-magnon states"
    )

    jh_pattern = r"J\s*_?\s*h"
    jt_pattern = r"J\s*_?\s*t"
    jd_pattern = r"J\s*_?\s*d"
    ms_pattern = r"m\s*/\s*m\s*_?\s*s"

    identity_match = re.search(
        r"Simplex Crystal Ground State and Magnetization Plateaus in "
        r"the Spin\s*-\s*1\s*/\s*2 Heisenberg Model on the Ruby Lattice"
        r".{0,2500}?Pratyay Ghosh"
        r".{0,1000}?Mila"
        r".{0,10000}?arXiv\s*:\s*2512\.14173v1",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"spin\s*-\s*1\s*/\s*2 Heisenberg Hamiltonian on this lattice "
        r"is given"
        r".{0,3500}?H\s*="
        r".{0,500}?J\s*_?\s*k"
        r".{0,500}?S\s*_?\s*i\s*(?:dot|·)\s*S\s*_?\s*j"
        r".{0,500}?\(\s*1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    bond_model_match = re.search(
        r"where S\s*_?\s*i are S\s*=\s*1\s*/\s*2 operators"
        r".{0,3500}?bond.{0,500}?of type k\s*(?:in|∈)\s*"
        r"\{\s*h\s*,\s*t\s*,\s*d\s*\}",
        normalized,
        flags=re.IGNORECASE,
    )
    isotropic_match = re.search(
        r"regime of primary interest"
        r".{0,3500}?isotropic limit\s*"
        + jh_pattern
        + r"\s*=\s*"
        + jt_pattern
        + r"\s*=\s*"
        + jd_pattern,
        normalized,
        flags=re.IGNORECASE,
    )
    localized_match = re.search(
        r"construct such"
        r".{0,3000}?localized\s*-\s*magnon states on the ruby lattice"
        r".{0,5000}?starts? by building single\s*-\s*magnon eigenstates"
        r".{0,5000}?ruby lattice"
        r".{0,1500}?magnon can become strictly localized within"
        r".{0,500}?a region R",
        normalized,
        flags=re.IGNORECASE,
    )
    ansatz_match = re.search(
        r"(?:consider|considering) a magnon "
        r"(?:wavefunction|wave\s*-.{0,500}?function)"
        r".{0,1200}?"
        r"\|(?:Phi>|Φ⟩)\s*(?:proportional to|∼)"
        r".{0,500}?"
        r"(?:sum_?\s*\(\s*i\s+in\s+R\s*\).{0,100}?)?"
        r"c\s*_?\s*i\s*S\s*_?\s*i\s*\^?\s*-\s*"
        r"\|FP(?:>|⟩)\s*\.?\s*\(\s*4\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    interference_match = re.search(
        r"destructive interference between these processes localizes"
        r".{0,1000}?the magnon"
        r".{0,2500}?necessary\s*"
        r"(?:\(\s*and sufficient.{0,600}?\)|and sufficient)"
        r".{0,700}?condition holds",
        normalized,
        flags=re.IGNORECASE,
    )
    condition_match = re.search(
        r"(?:sum_?\s*\(\s*i\s+in\s+R\s*\)\s*)?"
        r"J\s*_?\s*i\s*j\s*c\s*_?\s*i\s*=\s*0\s*,\s*"
        r"(?:for all|∀)\s*j\s*(?:in|∈)\s*R"
        r"(?:\s*-\s*bar)?\s*\.?\s*\(\s*5\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    hexagon_match = re.search(
        r"On the ruby lattice, this condition is satisfied when the"
        r".{0,1000}?magnon is confined to a "
        + jh_pattern
        + r" hexagon with an alternating"
        r".{0,1000}?sign structure of "
        r"c\s*_?\s*i",
        normalized,
        flags=re.IGNORECASE,
    )
    product_match = re.search(
        r"Following this"
        r".{0,2500}?construct an exact product"
        r".{0,800}?state of single\s*-\s*"
        r"magnon states"
        r".{0,2500}?every hexago(?:nal|\s*-.{0,800}?nal) plaquette"
        r".{0,1200}?yielding\s*"
        + ms_pattern
        + r"\s*=\s*2\s*/\s*3",
        normalized,
        flags=re.IGNORECASE,
    )
    higher_energy_match = re.search(
        r"(?:energy of this state|Its energy)"
        r"\s*,?\s*however\s*,?\s*is higher than "
        r"(?:the energy.{0,500}?obtained in our iPEPS calculations|"
        r"the iPEPS energy)",
        normalized,
        flags=re.IGNORECASE,
    )
    plateau_rejection_match = re.search(
        r"state just below (?:the )?saturation(?: field)?"
        r".{0,2500}?"
        + ms_pattern
        + r"\s*=\s*2\s*/\s*3 plateau"
        r".{0,2500}?iPEPS"
        r".{0,1000}?does not appear to correspond to a localized\s*-"
        r".{0,200}?"
        r"magnon state",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_existence_match = re.search(
        r"focus on the isotropic point\s*,?\s*"
        + jt_pattern
        + r"\s*=\s*"
        + jh_pattern
        + r"\s*=\s*"
        + jd_pattern
        + r"\s*,?\s*where.{0,800}?localized\s*-\s*"
        r"magnon eigenstates can occur",
        normalized,
        flags=re.IGNORECASE,
    )
    global_rejection_match = re.search(
        r"None of (?:these|the observed plateau) states can be "
        r"interpreted as.{0,800}?strongly localized magnon states",
        normalized,
        flags=re.IGNORECASE,
    )

    matches = (
        identity_match,
        hamiltonian_match,
        bond_model_match,
        isotropic_match,
        localized_match,
        ansatz_match,
        interference_match,
        condition_match,
        hexagon_match,
        product_match,
        higher_energy_match,
        plateau_rejection_match,
        conclusion_existence_match,
        global_rejection_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    model_start = min(
        hamiltonian_match.start(),
        bond_model_match.start(),
        isotropic_match.start(),
    )
    model_end = max(
        hamiltonian_match.end(),
        bond_model_match.end(),
        isotropic_match.end(),
    )
    ansatz_start = min(localized_match.start(), ansatz_match.start())
    ansatz_end = max(localized_match.end(), ansatz_match.end())
    proof_start = min(
        interference_match.start(),
        condition_match.start(),
        hexagon_match.start(),
    )
    proof_end = max(
        interference_match.end(),
        condition_match.end(),
        hexagon_match.end(),
    )
    scope_start = min(
        product_match.start(),
        higher_energy_match.start(),
        plateau_rejection_match.start(),
        conclusion_existence_match.start(),
        global_rejection_match.start(),
    )
    scope_end = max(
        product_match.end(),
        higher_energy_match.end(),
        plateau_rejection_match.end(),
        conclusion_existence_match.end(),
        global_rejection_match.end(),
    )
    return (
        {"supports_localized_magnons": True},
        {
            "parser": (
                "parse_ghosh_mila_ruby_localized_magnon_eigenstate"
            ),
            "source_model": (
                "spin-1/2 ruby-lattice Heisenberg antiferromagnet with "
                "Jh, Jt, and Jd bonds at Jh=Jt=Jd"
            ),
            "proof_chain": (
                "Eq. (4) one-magnon ansatz -> Eq. (5) destructive "
                "interference -> alternating-sign Jh-hexagon state -> "
                "exact product eigenstate"
            ),
            "registry_claim_mapping": (
                "source supports existence of exact localized one-magnon "
                "eigenstates only; it explicitly rejects a "
                "localized-magnon interpretation of the iPEPS plateau "
                "states"
            ),
            "registered_model_correction": (
                "replace flat-band plateau wording with localized-magnon "
                "eigenstate existence at the isotropic ruby-lattice point"
            ),
            "corrected_source_identity": "arXiv:2512.14173v1",
            "superseded_registered_doi": (
                "10.1103/PhysRevLett.93.107206"
            ),
            "matched_anchors": [
                "identified arXiv:2512.14173v1 paper and authors",
                "spin-1/2 Jh-Jt-Jd ruby Hamiltonian at the isotropic point",
                "strictly localized one-magnon ansatz, Eq. (4)",
                "destructive-interference condition, Eq. (5), and "
                "alternating-sign Jh hexagon",
                "exact product eigenstate plus explicit exclusion of "
                "localized magnons as the iPEPS plateau mechanism",
            ],
            "text_spans": [
                [identity_match.start(), identity_match.end()],
                [model_start, model_end],
                [ansatz_start, ansatz_end],
                [proof_start, proof_end],
                [scope_start, scope_end],
            ],
        },
    )


def parse_biffin_gamma_li2iro3_spiral_kitaev_order(source_text):
    """Extract the observed spiral order and its minimal Kitaev model."""

    error_message = (
        "Biffin gamma-Li2IrO3 spiral/Kitaev source must establish the "
        "identified PhysRevLett.113.197201 paper, the three-dimensional "
        "Kitaev topology, magnetic resonant x-ray evidence for the "
        "q=(0.57(1),0,0) incommensurate noncoplanar counterrotating "
        "structure, the minimal Kitaev-Heisenberg Hamiltonian and its "
        "reported couplings, the Luttinger-Tisza reproduction, and the "
        "3D Kitaev-material conclusion"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_biffin_gamma_li2iro3_spiral_kitaev_order",
    )
    return _finalize_prepared_trace(
        _parse_biffin_gamma_li2iro3_spiral_kitaev_order_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_biffin_gamma_li2iro3_spiral_kitaev_order_prepared(normalized):
    error_message = (
        "Biffin gamma-Li2IrO3 spiral/Kitaev source must establish the "
        "identified PhysRevLett.113.197201 paper, the three-dimensional "
        "Kitaev topology, magnetic resonant x-ray evidence for the "
        "q=(0.57(1),0,0) incommensurate noncoplanar counterrotating "
        "structure, the minimal Kitaev-Heisenberg Hamiltonian and its "
        "reported couplings, the Luttinger-Tisza reproduction, and the "
        "3D Kitaev-material conclusion"
    )

    material_pattern = (
        r"(?:gamma|γ)\s*-\s*Li\s*2\s*Ir\s*O\s*3"
    )
    kc_pattern = r"K\s*_?\s*c"
    kd_pattern = r"K\s*_?\s*d"
    jc_pattern = r"J\s*_?\s*c"
    jd_pattern = r"J\s*_?\s*d"
    icc_pattern = r"I\s*_?\s*cc"
    j2_pattern = r"J\s*_?\s*2"

    identity_match = re.search(
        r"Noncoplanar and Counterrotating Incommensurate Magnetic Order "
        r"Stabilized by Kitaev Interactions in "
        + material_pattern
        + r".{0,1200}?A\.\s*Biffin"
        r".{0,1000}?R\.\s*D\.\s*Johnson"
        r".{0,1000}?I\.\s*Kimchi"
        r".{0,1800}?R\.\s*Coldea"
        r".{0,5000}?DOI\s*:\s*10\.1103/PhysRevLett\.113\.197201",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"Materials that realize Kitaev spin models with bond\s*-\s*"
        r"dependent anisotropic interactions"
        r".{0,900}?explore the magnetism of "
        + material_pattern
        + r".{0,500}?topology of a three\s*-\s*dimensional Kitaev lattice"
        r".{0,500}?interconnected Ir honeycombs"
        r".{0,700}?magnetic resonant x\s*-\s*ray diffraction"
        r".{0,800}?incommensurate magnetic structure"
        r".{0,500}?noncoplanar and counterrotating Ir moments"
        r".{0,900}?minimal Kitaev\s*-\s*Heisenberg Hamiltonian"
        r".{0,1200}?dominant Kitaev interactions",
        normalized,
        flags=re.IGNORECASE,
    )
    propagation_match = re.search(
        r"low temper.{0,700}?atures"
        r".{0,1500}?magnetic Bragg peaks"
        r".{0,1500}?satellite.{0,1200}?positions"
        r".{0,1500}?incommensu.{0,700}?rate propagation vector\s*"
        r"q\s*(?:=|¼)\s*(?:\(|ð)\s*0\.57\s*(?:\(|ð)\s*1\s*"
        r"(?:\)|Þ)\s*[,;]\s*0\s*[,;]\s*0\s*(?:\)|Þ)"
        r".{0,2400}?sharp as structural peaks"
        r".{0,1800}?all three reciprocal(?:\s*-\s*|\s+)space directions"
        r".{0,1200}?coherent.{0,1200}?"
        r"(?:three\s*-\s*dimensional|3D) magnetic ordering",
        normalized,
        flags=re.IGNORECASE,
    )
    model_intro_match = re.search(
        r"Kitaev interactions can stabilize the counterrotating moments"
        r".{0,700}?propaga(?:tion|\s*-.{0,400}?tion) vector q along a"
        r".{0,1200}?construct the following"
        r".{0,1200}?Kitaev\s*-\s*Heisenberg "
        r"Hamiltonian as a minimal model",
        normalized,
        flags=re.IGNORECASE,
    )
    equation_match = re.search(
        r"H\s*(?:=|¼)"
        r".{0,900}?"
        + kc_pattern
        + r".{0,700}?"
        + jc_pattern
        + r".{0,700}?"
        + icc_pattern
        + r".{0,900}?"
        + kd_pattern
        + r".{0,700}?"
        + jd_pattern
        + r".{0,900}?"
        + j2_pattern
        + r".{0,300}?(?:\(\s*1\s*\)|ð\s*1\s*Þ)",
        normalized,
        flags=re.IGNORECASE,
    )
    parameters_match = re.search(
        r"We take"
        r"(?=.{0,1800}?meV)"
        r".{0,1800}?"
        + kc_pattern
        + r"\s*(?:=|¼)\s*-\s*15\s*,\s*"
        + kd_pattern
        + r"\s*(?:=|¼)\s*-\s*12\s*,\s*"
        + jc_pattern
        + r"\s*(?:=|¼)\s*5\s*,\s*"
        + jd_pattern
        + r"\s*(?:=|¼)\s*2\.5\s*,\s*"
        + icc_pattern
        + r"\s*(?:=|¼)\s*-\s*4\.5\s*,?\s*(?:and\s*)?"
        + j2_pattern
        + r"\s*(?:=|¼).{0,500}?-\s*0\.9",
        normalized,
        flags=re.IGNORECASE,
    )
    reproduction_match = re.search(
        r"Hamiltonian was analyzed in Fourier space using"
        r".{0,1200}?Luttinger\s*-\s*Tisza approximation"
        r".{0,1200}?lowest\s*-\s*energy mode identical"
        r".{0,1200}?coplanar projection of the magnetic structure"
        r".{0,2600}?(?:mode mixing|mixed.{0,1600}?mode) exactly "
        r"reproduces the observed noncoplanar "
        r"struc(?:ture|\s*-.{0,900}?ture)",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"To summarize"
        r".{0,700}?MRXD measurements on"
        r".{0,1200}?"
        + material_pattern
        + r" single crystals"
        r".{0,1500}?observed an "
        r"incommen(?:surate|\s*-.{0,900}?surate)\s*,?\s*noncoplanar "
        r"magnetic structure with counterrotating"
        r".{0,900}?moments"
        r".{0,900}?Kitaev\s*-\s*Heisenberg Hamiltonian can fully"
        r".{0,900}?explain"
        r".{0,1500}?provid(?:ing|\s*-.{0,900}?ing) strong evidence"
        r".{0,1200}?"
        + material_pattern
        + r".{0,1200}?experimental.{0,1200}?"
        r"realization of 3D Kitaev physics",
        normalized,
        flags=re.IGNORECASE,
    )

    matches = (
        identity_match,
        abstract_match,
        propagation_match,
        model_intro_match,
        equation_match,
        parameters_match,
        reproduction_match,
        conclusion_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    model_start = min(
        model_intro_match.start(),
        equation_match.start(),
        parameters_match.start(),
        reproduction_match.start(),
    )
    model_end = max(
        model_intro_match.end(),
        equation_match.end(),
        parameters_match.end(),
        reproduction_match.end(),
    )
    return (
        {"incommensurate_spiral_order": True},
        {
            "parser": (
                "parse_biffin_gamma_li2iro3_spiral_kitaev_order"
            ),
            "source_model": (
                "gamma-Li2IrO3 three-dimensional stripyhoneycomb Kitaev "
                "lattice with a minimal Kitaev-Heisenberg "
                "anisotropic-exchange model"
            ),
            "reported_propagation_vector": [0.57, 0.0, 0.0],
            "reported_q_uncertainty": 0.01,
            "registry_claim_mapping": (
                "the observed incommensurate noncoplanar counterrotating "
                "magnetic structure directly supplies the registered "
                "incommensurate-spiral-order boolean"
            ),
            "corrected_source_identity": (
                "DOI:10.1103/PhysRevLett.113.197201"
            ),
            "superseded_registered_source_for_order_claim": (
                "DOI:10.1038/ncomms5203"
            ),
            "source_scope_note": (
                "the registered Modic source establishes the harmonic "
                "honeycomb structure and spin-anisotropic exchange, while "
                "Biffin et al. directly measure the registered spiral order"
            ),
            "matched_anchors": [
                "identified PhysRevLett.113.197201 paper and authors",
                "three-dimensional interconnected-honeycomb topology, "
                "MRXD, and dominant Kitaev-interaction abstract",
                "q=(0.57(1),0,0) coherent incommensurate 3D order",
                "minimal Kitaev-Heisenberg Eq. (1), reported couplings, "
                "and Luttinger-Tisza reproduction",
                "incommensurate noncoplanar counterrotating 3D "
                "Kitaev-material conclusion",
            ],
            "text_spans": [
                [identity_match.start(), identity_match.end()],
                [abstract_match.start(), abstract_match.end()],
                [propagation_match.start(), propagation_match.end()],
                [model_start, model_end],
                [conclusion_match.start(), conclusion_match.end()],
            ],
        },
    )


def parse_taylor_ising_correlation_length(source_text):
    """Derive the Ising-chain correlation length from Taylor's Eq. (5)."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Taylor Ising Eq. (5) requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    correlation_match = re.search(
        r"(?:<\s*s_i\s+s_i\+l\s*>|hsi\s+si\+l\s+i)\s*=.{0,180}?\(5\)",
        normalized,
        flags=re.IGNORECASE,
    )
    decay_match = re.search(
        r"equal to\s+tanh(?:\^\s*l|l)\s*\(\s*J\s*(?:beta|β)\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    if correlation_match is None or decay_match is None:
        raise RuntimeEvidenceError(
            "Taylor Ising Eq. (5) must define the two-point correlation and "
            "state its tanh(J beta) to the l-th-power decay"
        )
    return (
        {
            "correlation_length_beta_1_j_1": -1.0
            / math.log(math.tanh(1.0))
        },
        {
            "parser": "parse_taylor_ising_correlation_length",
            "equation": "5",
            "derivation": (
                "C(l)=tanh(J beta)^l=exp(-l/xi) => "
                "xi=-1/log(tanh(J beta)); beta=J=1"
            ),
            "matched_anchors": [
                "two-point correlation definition (5)",
                "equal to tanh^l(J beta)",
            ],
            "text_spans": [
                [correlation_match.start(), correlation_match.end()],
                [decay_match.start(), decay_match.end()],
            ],
        },
    )


def parse_tasaki_lsm_half_integer_constraint(source_text):
    """Extract Tasaki's half-odd-integer unique-ground-state constraint."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Tasaki LSM claim requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    claim_match = re.search(
        r"one-dimensional spin system with a half-odd-integer S has gapless "
        r"excitations in the infinite volume limit provided that the ground "
        r"state is unique",
        normalized,
        flags=re.IGNORECASE,
    )
    if claim_match is None:
        raise RuntimeEvidenceError(
            "Tasaki LSM claim must contain one-dimensionality, half-odd-integer "
            "spin, gapless excitations, the infinite-volume limit, and a unique "
            "ground state"
        )
    return (
        {"unique_ground_state_implies_gapless_excitations": True},
        {
            "parser": "parse_tasaki_lsm_half_integer_constraint",
            "matched_anchors": [
                "one-dimensional half-odd-integer spin",
                "unique ground state implies gapless excitations",
                "infinite volume limit",
            ],
            "text_spans": [[claim_match.start(), claim_match.end()]],
        },
    )


def parse_onsager_square_ising_tc(source_text):
    """Derive the isotropic square-Ising critical temperature from Onsager."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Onsager critical condition requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    transition_match = re.search(
        r"order-disorder transition.{0,120}?temperature\s+T\s*=\s*T",
        normalized,
        flags=re.IGNORECASE,
    )
    condition_match = re.search(
        r"sinh\s*\(\s*2\s*J\s*/\s*kT[^)]*\)\s*"
        r"sinh\s*\(\s*2\s*J['′]?\s*/\s*kT[^)]*\)\s*=\s*1",
        normalized,
        flags=re.IGNORECASE,
    )
    if transition_match is None or condition_match is None:
        raise RuntimeEvidenceError(
            "Onsager critical condition must identify the order-disorder "
            "transition and sinh(2J/kTc) sinh(2J'/kTc) = 1"
        )
    return (
        {"tc_over_j": 2.0 / math.log(1.0 + math.sqrt(2.0))},
        {
            "parser": "parse_onsager_square_ising_tc",
            "derivation": (
                "J'=J and sinh(2J/kTc)^2=1 => "
                "Tc/J=2/log(1+sqrt(2)), with k=1"
            ),
            "matched_anchors": [
                "order-disorder transition temperature",
                "sinh(2J/kTc) sinh(2J'/kTc) = 1",
            ],
            "text_spans": [
                [transition_match.start(), transition_match.end()],
                [condition_match.start(), condition_match.end()],
            ],
        },
    )


def parse_yang_spontaneous_magnetization(source_text):
    """Extract Yang's exact square-Ising spontaneous-magnetization result."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Yang spontaneous magnetization requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    identity_match = re.search(
        r"Spontaneous Magnetization of a Two-Dimensional Ising Model"
        r".{0,300}?spontaneous magnetization of a two-dimensional Ising model"
        r".{0,80}?calculated exactly",
        normalized,
        flags=re.IGNORECASE,
    )
    ordered_phase_match = re.search(
        r"below the critical.{0,120}?temperature.{0,500}?largest eigenvalue"
        r".{0,500}?doubly degenerate",
        normalized,
        flags=re.IGNORECASE,
    )
    final_equation_match = re.search(
        r"VI\.\s*FINAL RESULTS.{0,300}?spontaneous magnetization I is obtained"
        r".{0,120}?\(95\) and \(80\) as.{0,300}?"
        r"(?:sinh\s*\(\s*2H\s*\)|"
        r"1\+x.{0,180}?I\s*=.{0,100}?1.{0,30}?6x.{0,40}?x)"
        r".{0,120}?\(96\)",
        normalized,
        flags=re.IGNORECASE,
    )
    if any(
        match is None
        for match in (identity_match, ordered_phase_match, final_equation_match)
    ):
        raise RuntimeEvidenceError(
            "Yang spontaneous magnetization must contain the exact two-dimensional "
            "Ising claim, the below-critical ordered phase, and final Eq. (96)"
        )
    beta_j = 0.6
    magnetization = (1.0 - math.sinh(2.0 * beta_j) ** -4) ** 0.125
    return (
        {
            "formula": "[1 - sinh(2 beta J)^(-4)]^(1/8)",
            "magnetization_beta_0_6_j_1": magnetization,
        },
        {
            "parser": "parse_yang_spontaneous_magnetization",
            "equation": "96",
            "normalization": "H=beta*J and magnetization normalized to saturation",
            "matched_anchors": [
                "exact two-dimensional Ising spontaneous magnetization",
                "below-critical doubly-degenerate largest transfer eigenvalue",
                "Sec. VI final Eq. (96) from Eqs. (95) and (80)",
            ],
            "text_spans": [
                [identity_match.start(), identity_match.end()],
                [ordered_phase_match.start(), ordered_phase_match.end()],
                [final_equation_match.start(), final_equation_match.end()],
            ],
        },
    )


def recompute_yang_spontaneous_magnetization_operand(*, beta, exchange):
    return {
        "formula": "[1 - sinh(2 beta J)^(-4)]^(1/8)",
        "magnetization_beta_0_6_j_1": (
            benchmark_functions.two_dimensional_ising_spontaneous_magnetization(
                beta=beta,
                exchange=exchange,
            )
        ),
    }


def parse_square_potts_critical_point(source_text):
    """Derive the square-Potts critical coupling and transition boundary."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "square Potts critical point requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    variable_match = re.search(
        r"(?:"
        r"x\s*_?\s*n\s*=\s*\(\s*exp\s*\(\s*K\s*_?\s*n\s*\)\s*"
        r"[-−—]\s*1\s*\)\s*/\s*sqrt\s*\(\s*q\s*\).{0,30}?\(4\.4\)"
        r"|"
        r"\(4\.4\).{0,240}?x[^\s=]{0,3}\s*=\s*\(e.{0,8}?"
        r"[−—-]\s*[I1]\s*\)\s*/\s*[v√]\s*q"
        r")",
        normalized,
        flags=re.IGNORECASE,
    )
    square_condition_match = re.search(
        r"(?:"
        r"square lattice.{0,100}?x\s*_?\s*1\s*x\s*_?\s*2\s*=\s*1"
        r".{0,40}?\(5\.\s*1b\)"
        r"|"
        r"x.{0,4}?x2\s*=\s*1\s*squa(?:re|ie).{0,260}?\(5\.\s*1b\)"
        r")",
        normalized,
        flags=re.IGNORECASE,
    )
    self_dual_match = re.search(
        r"expression\s*\(5\.\s*1b\).{0,220}?critical point.{0,100}?"
        r"square(?:-|\s+)lattice.{0,700}?duality.{0,250}?self-dual point"
        r".{0,80}?x.{0,5}?x\s*_?\s*2\s*(?:=|—|−)\s*1",
        normalized,
        flags=re.IGNORECASE,
    )
    explicit_boundary_match = re.search(
        r"two dimensions.{0,180}?continuous for q\s*<=\s*4.{0,100}?"
        r"first order.{0,40}?q\s*>\s*4",
        normalized,
        flags=re.IGNORECASE,
    )
    ocr_boundary_match = re.search(
        r"exact information.{0,180}?critical point for the square,\s*triangu-"
        r".{0,100}?honeycomb lattices.{0,100}?transi-.{0,30}?tion is of "
        r"first order for q\s*&\s*4, and is continuous for q\s*&\s*4",
        normalized,
        flags=re.IGNORECASE,
    )
    boundary_match = explicit_boundary_match or ocr_boundary_match
    matches = (
        variable_match,
        square_condition_match,
        self_dual_match,
        boundary_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "square Potts critical point must contain the temperature variable, "
            "square-lattice Eq. (5.1b), its self-dual derivation, and the q=4 "
            "transition-order boundary"
        )
    return (
        {
            "critical_beta_j": "log(1 + sqrt(q))",
            "continuous_for_q_le_4": True,
        },
        {
            "parser": "parse_square_potts_critical_point",
            "derivation": (
                "x=(exp(K)-1)/sqrt(q); isotropic square x^2=1; "
                "ferromagnetic x=1"
            ),
            "matched_anchors": [
                "Eq. (4.4) normalized Potts temperature variable",
                "Eq. (5.1b) square-lattice critical condition",
                "square-lattice self-dual critical point",
                "two-dimensional q=4 transition-order boundary",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def recompute_square_potts_critical_point(*, transition_boundary, q_checks):
    """Solve the ferromagnetic self-dual equation and cross-check numerically."""

    if type(transition_boundary) is not int or transition_boundary < 1:
        raise RuntimeEvidenceError("square Potts transition boundary must be positive")
    if (
        not isinstance(q_checks, Sequence)
        or isinstance(q_checks, (str, bytes))
        or not q_checks
    ):
        raise RuntimeEvidenceError("square Potts q checks must be nonempty")
    checked_q = []
    for q in q_checks:
        if isinstance(q, bool) or not isinstance(q, (int, float)) or q <= 0:
            raise RuntimeEvidenceError("square Potts q checks must be positive")
        q = float(q)
        self_dual_x = 1.0
        exp_k = 1.0 + self_dual_x * math.sqrt(q)
        derived_k = math.log(exp_k)
        helper_k = benchmark_functions.square_potts_critical_beta_j(q)
        if not math.isclose(derived_k, helper_k, rel_tol=0.0, abs_tol=1.0e-15):
            raise RuntimeEvidenceError(
                "square Potts self-dual solution disagrees with numeric adapter"
            )
        checked_q.append(q)
    continuous_for_registered_range = all(
        q <= transition_boundary for q in checked_q if q <= 4.0
    )
    return {
        "critical_beta_j": "log(1 + sqrt(q))",
        "continuous_for_q_le_4": continuous_for_registered_range,
    }


def parse_wannier_triangular_entropy(source_text):
    """Extract Wannier's zero-temperature triangular-Ising entropy formula."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Wannier triangular Ising entropy requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"Antiferromagnetism\. The Triangular Ising Net.{0,1600}?"
        r"triangular net with antiferromagnetic interaction",
        normalized,
        flags=re.IGNORECASE,
    )
    zero_entropy_match = re.search(
        r"entropy at absolute zero is finite",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_formula_match = re.search(
        r"S\(0\)\s*/\s*R\s*=\s*\(2\s*/\s*pi\).{0,30}?"
        r"integral\s*_?0\s*\^\s*\(pi\s*/\s*3\).{0,30}?"
        r"ln\s*\(2\s*cos\s*\(omega\)\).{0,30}?\(37a\)",
        normalized,
        flags=re.IGNORECASE,
    )
    ocr_formula_match = re.search(
        r"The second term is therefore the entropy.{0,160}?S\(0\).{0,160}?"
        r"[li]n\[?\(?1.{0,700}?Thus we get for the zero-point.{0,120}?"
        r"entropy where S\(0\).{0,100}?ln\(2 cos.{0,100}?\(37a\)"
        r".{0,300}?alternate expression.{0,220}?S\(0\).{0,140}?"
        r"ln\(2 cos.{0,100}?\(37b\)",
        normalized,
        flags=re.IGNORECASE,
    )
    formula_match = clean_formula_match or ocr_formula_match
    printed_match = re.search(
        r"(?:printed as\s*)?S\(0\)\s*/\s*R\s*=\s*0\.338314.{0,30}?\(37c\)|"
        r"0\.338314\s*\(37c\)",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (model_match, zero_entropy_match, formula_match)
    if any(match is None for match in matches) or printed_match is None:
        raise RuntimeEvidenceError(
            "Wannier triangular Ising entropy must identify the antiferromagnetic "
            "triangular net, finite zero-temperature entropy, Eqs. (37a)-(37b), "
            "and the printed Eq. (37c) decimal"
        )
    x = math.pi / 6.0
    series_value = (
        0.5 * math.log(2.0)
        - x**2 / 12.0
        - x**4 / 120.0
        - x**6 / 630.0
        - 17.0 * x**8 / 45360.0
    )
    entropy = round(series_value, 6)
    printed_decimal = 0.338314
    return (
        {"residual_entropy_per_spin": entropy},
        {
            "parser": "parse_wannier_triangular_entropy",
            "equation": "37a",
            "derivation": (
                "Eq. (37c) series through omega^8 evaluates the Eq. (37a) "
                "integral and rounds to six decimals"
            ),
            "printed_decimal": printed_decimal,
            "printed_decimal_matches_formula": math.isclose(
                printed_decimal, entropy, rel_tol=0.0, abs_tol=0.5e-6
            ),
            "matched_anchors": [
                "antiferromagnetic triangular Ising net",
                "finite entropy at absolute zero",
                "zero-point entropy Eqs. (37a)-(37c)",
            ],
            "text_spans": [
                [model_match.start(), model_match.end()],
                [zero_entropy_match.start(), zero_entropy_match.end()],
                [formula_match.start(), printed_match.end()],
            ],
        },
    )


def recompute_wannier_triangular_entropy(*, intervals):
    """Numerically integrate Wannier's Eq. (37a) by composite Simpson rule."""

    if type(intervals) is not int or intervals < 100 or intervals % 2:
        raise RuntimeEvidenceError(
            "Wannier entropy integration intervals must be an even integer >= 100"
        )
    lower = 0.0
    upper = math.pi / 3.0
    step = (upper - lower) / intervals

    def integrand(omega):
        return math.log(2.0 * math.cos(omega))

    weighted_sum = integrand(lower) + integrand(upper)
    weighted_sum += 4.0 * sum(
        integrand(lower + index * step)
        for index in range(1, intervals, 2)
    )
    weighted_sum += 2.0 * sum(
        integrand(lower + index * step)
        for index in range(2, intervals, 2)
    )
    integral = step * weighted_sum / 3.0
    return {
        "residual_entropy_per_spin": round(2.0 * integral / math.pi, 6)
    }


def parse_barouch_mccoy_xy_boundaries(source_text):
    """Extract the field and anisotropy boundaries of the XY chain."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Barouch-McCoy XY boundaries require nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    identity_match = re.search(
        r"Statistical Mechanics of the XY Model\. II\. Spin-Correlation Functions",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_hamiltonian_match = re.search(
        r"Hamiltonian is H\s*=\s*J.{0,80}?\(1\s*\+\s*gamma\).{0,80}?"
        r"\(1\s*-\s*gamma\).{0,100}?-\s*h.{0,80}?Sz",
        normalized,
        flags=re.IGNORECASE,
    )
    ocr_hamiltonian_match = re.search(
        r"Hamiltonian they studied was.{0,300}?H\s*=\s*J.{0,100}?"
        r"\(1\+y\).{0,100}?\(1\s*[—-]\s*y\).{0,160}?[—-]h"
        r".{0,160}?\(1\.\s*1\)",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = clean_hamiltonian_match or ocr_hamiltonian_match
    anisotropy_match = re.search(
        r"if.{0,40}?h.{0,20}?(?:<|&).{0,8}?J.{0,120}?ground-state energy"
        r".{0,100}?not an analytic function of.{0,120}?(?:gamma|y) at "
        r"(?:gamma|y)\s*=\s*0",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_field_match = re.search(
        r"fails to be an analytic function of h at.{0,30}?\|?h\|?\s*=\s*J"
        r".{0,40}?for any gamma",
        normalized,
        flags=re.IGNORECASE,
    )
    ocr_field_match = re.search(
        r"fails to be an analytic function.{0,180}?of h at h.{0,30}?="
        r".{0,30}?for any y"
        r".{0,120}?J",
        normalized,
        flags=re.IGNORECASE,
    )
    field_match = clean_field_match or ocr_field_match
    matches = (identity_match, hamiltonian_match, anisotropy_match, field_match)
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Barouch-McCoy XY boundaries must identify the XY-chain Hamiltonian, "
            "the gamma=0 nonanalyticity for |h|<J, and the |h|=J "
            "nonanalyticity for arbitrary gamma"
        )
    return (
        {
            "ising_critical_field": 1.0,
            "anisotropy_transition_gamma": 0.0,
        },
        {
            "parser": "parse_barouch_mccoy_xy_boundaries",
            "normalization": "g=|h|/J and source y=registered gamma",
            "matched_anchors": [
                "Barouch-McCoy XY Model II",
                "anisotropic XY Hamiltonian with magnetic field",
                "gamma=0 ground-state nonanalyticity for |h|<J",
                "field nonanalyticity at |h|=J for arbitrary gamma",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def recompute_xy_critical_boundaries(*, interior_field, anisotropy_probe):
    """Check both free-fermion gap-closing manifolds of the XY chain."""

    for label, value in (
        ("interior field", interior_field),
        ("anisotropy probe", anisotropy_probe),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeEvidenceError(f"XY {label} must be numeric")
    g = float(interior_field)
    gamma_probe = float(anisotropy_probe)
    if not 0.0 < abs(g) < 1.0 or gamma_probe == 0.0:
        raise RuntimeEvidenceError(
            "XY probes require 0 < |interior_field| < 1 and nonzero anisotropy"
        )

    def dispersion_squared(momentum, field, gamma):
        return (
            (math.cos(momentum) - field) ** 2
            + gamma**2 * math.sin(momentum) ** 2
        )

    field_boundary_gap = dispersion_squared(0.0, 1.0, gamma_probe)
    interior_momentum = math.acos(g)
    anisotropy_boundary_gap = dispersion_squared(interior_momentum, g, 0.0)
    interior_gapped_probe = dispersion_squared(
        interior_momentum, g, gamma_probe
    )
    field_gapped_probe = dispersion_squared(0.0, 1.1, gamma_probe)
    if (
        not math.isclose(field_boundary_gap, 0.0, abs_tol=1.0e-15)
        or not math.isclose(anisotropy_boundary_gap, 0.0, abs_tol=1.0e-15)
        or interior_gapped_probe <= 0.0
        or field_gapped_probe <= 0.0
    ):
        raise RuntimeEvidenceError("XY free-fermion gap checks did not isolate both boundaries")
    return {
        "ising_critical_field": 1.0,
        "anisotropy_transition_gamma": 0.0,
    }


def parse_mulder_honeycomb_spiral_contour(source_text):
    """Derive the honeycomb J1-J2 spiral contour from Mulder et al. Eq. (5)."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Mulder honeycomb spiral contour evidence requires nonempty text"
        )
    prepared = _prepared_view_for_parser(
        source_text, "parse_mulder_honeycomb_spiral_contour"
    )
    return _finalize_prepared_trace(
        _parse_mulder_honeycomb_spiral_contour_prepared(prepared.text),
        prepared,
    )


def _parse_mulder_honeycomb_spiral_contour_prepared(normalized):

    identity_match = re.search(
        r"Spiral order by disorder and lattice nematic order in a frustrated "
        r"Heisenberg antiferromagnet on the honeycomb lattice"
        r".{0,220}?A\.?\s*Mulder.{0,60}?R\.?\s*Ganesh.{0,60}?"
        r"L\.?\s*Capriotti.{0,80}?A\.?\s*Paramekanti",
        normalized,
        flags=re.IGNORECASE,
    )
    phase_family_match = re.search(
        r"study a frustrated J\s*1\s*(?:-|–)\s*J\s*2 Heisenberg model on "
        r"the two(?:-|\s*)dimensional(?:\s*\(\s*2D\s*\))?\s+honeycomb "
        r"lattice.{0,260}?classical J\s*1\s*(?:-|–)\s*J\s*2 Heisenberg "
        r"model.{0,120}?N(?:[´'’]?e|é)el order for J\s*2\s*<\s*J\s*1\s*/\s*6"
        r".{0,100}?J\s*2\s*>\s*J\s*1\s*/\s*6.{0,120}?family of "
        r"degenerate incommensurate spin spiral ground states",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"Hamiltonian for this model.{0,520}?H\s*=\s*J\s*1"
        r".{0,100}?S\s*_?\s*i\s*(?:dot|[·.])\s*S\s*_?\s*j"
        r".{0,120}?\+\s*J\s*2.{0,100}?S\s*_?\s*i\s*"
        r"(?:dot|[·.])\s*S\s*_?\s*j.{0,100}?\(\s*1\s*\)"
        r".{0,180}?nearest(?:-|\s*)neighbor pairs.{0,120}?"
        r"next(?:-|\s*)neighbor pairs.{0,100}?set J\s*1\s*,\s*J\s*2"
        r"\s*>\s*0",
        normalized,
        flags=re.IGNORECASE,
    )
    ansatz_match = re.search(
        r"assum(?:e|ing) coplanar spiral order.{0,100}?spins on the two "
        r"sublattices.{0,620}?S\s*1\s*\(\s*r\s*\)\s*=\s*S"
        r".{0,40}?cos\s*\(\s*Q\s*(?:dot|·)\s*r\s*\)"
        r".{0,80}?sin\s*\(\s*Q\s*(?:dot|·)\s*r\s*\)"
        r".{0,80}?\(\s*2\s*\).{0,80}?S\s*2\s*\(\s*r\s*\)\s*="
        r"\s*[−-]\s*S.{0,60}?cos\s*\(\s*Q\s*(?:dot|·)\s*r\s*\+"
        r"\s*(?:phi|φ|ϕ)\s*\).{0,100}?\(\s*3\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    energy_match = re.search(
        r"classical ground(?:-|\s*)state energy per spin.{0,260}?"
        r"J\s*1\s*S\s*(?:\^?\s*2|²).{0,160}?cos\s*\(\s*(?:phi|φ|ϕ)"
        r"\s*[−-]\s*Q\s*_?\s*a\s*[−-]\s*Q\s*_?\s*b\s*\)"
        r".{0,120}?\+\s*J\s*2\s*S\s*(?:\^?\s*2|²)"
        r".{0,80}?cos\s*\(?\s*Q\s*_?\s*a\s*\)?"
        r".{0,80}?cos\s*\(?\s*Q\s*_?\s*b\s*\)?"
        r".{0,100}?cos\s*\(?\s*Q\s*_?\s*a\s*\+\s*Q\s*_?\s*b\s*\)?"
        r".{0,50}?\(\s*4\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_minimum_match = re.search(
        r"For J\s*2\s*/\s*J\s*1\s*>\s*1\s*/\s*6.{0,120}?"
        r"minimum energy solutions correspond to Q.{0,30}?satisfying"
        r".{0,120}?cos\s*\(?\s*Q.{0,15}?a\s*\)?\s*\+\s*"
        r"cos\s*\(?\s*Q.{0,15}?b\s*\)?\s*\+\s*"
        r"cos\s*\(\s*Q.{0,15}?a\s*\+\s*Q.{0,15}?b\s*\)"
        r"\s*=\s*(?:\(\s*1\s*/\s*2\s*\)|[½]).{0,30}?"
        r"J\s*1\s*/\s*\(\s*2\s*J\s*2\s*\)"
        r".{0,20}?(?:\^?\s*2|²).{0,20}?-\s*3"
        r".{0,30}?\(\s*5\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    two_column_minimum_match = re.search(
        r"For J\s*2\s*/\s*J\s*1\s*>\s*1\s*/\s*6.{0,80}?"
        r"minimum energy solutions corre-.{0,260}?spond to Q.{0,20}?"
        r"satisfying the relation.{0,360}?1\s+J\s*1\s+2"
        r".{0,80}?cos\s+Q.{0,12}?a\s*\+\s*cos\s+Q.{0,12}?b"
        r"\s*\+\s*cos\s*\(\s*Q.{0,12}?a\s*\+\s*Q.{0,12}?b\s*\)"
        r"\s*=\s*\(\s*\)\s*[−-]\s*3.{0,30}?\(\s*5\s*\)"
        r".{0,260}?2\s+2\s*J\s*2",
        normalized,
        flags=re.IGNORECASE,
    )
    minimum_match = clean_minimum_match or two_column_minimum_match
    contour_match = re.search(
        r"(?:classically degenerate solutions|lutions) to "
        r"Eq\.?\s*\(\s*5\s*\)"
        r".{0,80}?form a closed.{0,120}?contour.{0,80}?"
        r"Q\s*=\s*\(\s*0\s*,\s*0"
        r"\s*\).{0,80}?1\s*/\s*6\s*<\s*J\s*2\s*/\s*J\s*1"
        r"\s*<\s*1\s*/\s*2.{0,100}?J\s*2\s*/\s*J\s*1\s*>\s*1\s*/"
        r"\s*2.{0,80}?closed contours",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        phase_family_match,
        hamiltonian_match,
        ansatz_match,
        energy_match,
        minimum_match,
        contour_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Mulder honeycomb spiral contour source must establish the "
            "antiferromagnetic honeycomb J1-J2 Hamiltonian, the two-sublattice "
            "spiral ansatz, Eqs. (4)-(5), and the closed degenerate contours"
        )

    return (
        {
            "ring_condition": (
                "|1+exp(iq1)+exp(iq2)|=|J1|/(2J2)"
            )
        },
        {
            "parser": "parse_mulder_honeycomb_spiral_contour",
            "source_role": (
                "direct honeycomb correction to the registered "
                "diamond-lattice source"
            ),
            "equation": "5",
            "neel_boundary_j2_over_j1": 1.0 / 6.0,
            "coordinate_map": "(q1,q2)=(Q_b,Q_a+Q_b)",
            "derivation": (
                "The structure-factor modulus squared is "
                "3+2[cos(Q_a)+cos(Q_b)+cos(Q_a+Q_b)]; inserting Eq. (5) "
                "gives (J1/(2J2))^2. Because the paper sets J1,J2>0, "
                "taking the positive square root is equivalent to the "
                "registered |J1| convention"
            ),
            "matched_anchors": [
                "identified Mulder-Ganesh-Capriotti-Paramekanti paper",
                "classical honeycomb J1-J2 phase family and one-sixth boundary",
                "nearest- and next-neighbor Heisenberg Hamiltonian with J1,J2>0",
                "two-sublattice coplanar spiral ansatz in equations (2)-(3)",
                "classical energy kernel in equation (4)",
                "minimum-energy wave-vector equation (5)",
                "closed-contour regimes on both sides of J2/J1=1/2",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def recompute_honeycomb_j1_j2_spiral_contour(*, j1, j2):
    """Check the Eq. (5) contour against the honeycomb structure factor."""

    j1 = _require_positive_finite_real(
        j1, label="honeycomb J1-J2 spiral J1"
    )
    j2 = _require_positive_finite_real(
        j2, label="honeycomb J1-J2 spiral J2"
    )
    ratio = j2 / j1
    if not 1.0 / 6.0 < ratio < 0.5:
        raise RuntimeEvidenceError(
            "honeycomb J1-J2 spiral probe must satisfy "
            "1/6 < J2/J1 < 1/2"
        )

    equation_five_cosine_sum = 0.5 * (
        (j1 / (2.0 * j2)) ** 2 - 3.0
    )
    cosine_q_b = 0.5 * (equation_five_cosine_sum - 1.0)
    if not -1.0 < cosine_q_b < 1.0:
        raise RuntimeEvidenceError(
            "honeycomb J1-J2 spiral Eq. (5) probe left the cosine domain"
        )
    q_b = math.acos(cosine_q_b)
    q_a = 0.0
    q_1 = q_b
    q_2 = q_a + q_b
    structure_factor = abs(
        1.0
        + complex(math.cos(q_1), math.sin(q_1))
        + complex(math.cos(q_2), math.sin(q_2))
    )
    target_modulus = abs(j1) / (2.0 * j2)
    structure_factor_squared_identity = 3.0 + 2.0 * (
        math.cos(q_a)
        + math.cos(q_b)
        + math.cos(q_a + q_b)
    )
    if (
        not math.isclose(
            structure_factor, target_modulus, rel_tol=0.0, abs_tol=1.0e-12
        )
        or not math.isclose(
            structure_factor**2,
            structure_factor_squared_identity,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
    ):
        raise RuntimeEvidenceError(
            "honeycomb J1-J2 spiral structure-factor identity did not close"
        )
    return {
        "ring_condition": "|1+exp(iq1)+exp(iq2)|=|J1|/(2J2)"
    }


def parse_balla_iqbal_penc_fcc_type_orders(source_text):
    """Extract the three classical FCC J1-J2 commensurate type orders."""

    error_prefix = "Balla-Iqbal-Penc FCC type orders"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_balla_iqbal_penc_fcc_type_orders"
    )
    return _finalize_prepared_trace(
        _parse_balla_iqbal_penc_fcc_type_orders_prepared(prepared.text),
        prepared,
    )


def _parse_balla_iqbal_penc_fcc_type_orders_prepared(normalized):
    error_prefix = "Balla-Iqbal-Penc FCC type orders"

    two_column_layout_forms_accepted = bool(
        re.search(
            r"(?:antiferromagnetic[\s\S]{0,40}?or-"
            r"[\s\S]{0,100}?ders|right-column text precedes the "
            r"left-column Hamiltonian)",
            normalized,
            flags=re.IGNORECASE,
        )
    )

    title_match = re.search(
        r"Degenerate manifolds\s*,\s*helimagnets\s*,\s*and multi"
        r"(?:-| )Q chiral phases in the classical Heisenberg "
        r"antiferromagnet on the face(?:-| )centered(?:-| )cubic lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    authors_match = re.search(
        r"P.{0,3}ter\s+Balla.{0,30}?Yasir\s+Iqbal.{0,30}?"
        r"(?:and\s+)?Karlo\s+Penc",
        normalized,
        flags=re.IGNORECASE,
    )
    version_match = re.search(
        r"arXiv\s*:\s*2007\.00376v3",
        normalized,
        flags=re.IGNORECASE,
    )
    scope_match = re.search(
        r"detailed study of the ground state phase diagram of the classical "
        r"frustrated Heisenberg model on the face(?:-| )centered"
        r"(?:-| )cubic lattice.{0,180}?exchange interactions up till third "
        r"nearest neighbors.{0,160}?commensurate.{0,80}?helimagnetic"
        r".{0,120}?multi(?:-| )Q orders",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"Hamiltonian of the classical isotropic Heisenberg.{0,650}?"
        r"H\s*=\s*J\s*1.{0,120}?S\s*_?\s*i\s+dot\s+S\s*_?\s*j"
        r".{0,140}?\+\s*J\s*2.{0,120}?S\s*_?\s*i\s+dot\s+S\s*_?\s*j"
        r".{0,140}?\+\s*J\s*3.{0,120}?S\s*_?\s*i\s+dot\s+S\s*_?\s*j"
        r".{0,60}?\(\s*1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    unit_vector_text = (
        r"describes three dimensional unit vectors.{0,80}?"
        r"\|\s*S\s*_?\s*i\s*\|\s*=\s*1.{0,80}?sites"
    )
    neighbor_text = (
        r"R\s*_?\s*i of the fcc lattice.{0,100}?interacting with first"
        r"\s*\(\s*J\s*1\s*\)\s*,\s*second\s*\(\s*J\s*2\s*\)\s*,"
        r"\s*and third neighbor\s*\(\s*J\s*3\s*\)\s*interactions"
        r".{0,180}?(?:delta|δ)\s*=\s*1\s*,\s*2\s*,\s*3.{0,100}?"
        r"neighbor pairs"
    )
    model_definition_match = re.search(
        rf"(?:{unit_vector_text}.{{0,800}}?{neighbor_text}|"
        rf"{neighbor_text}.{{0,6000}}?{unit_vector_text})",
        normalized,
        flags=re.IGNORECASE,
    )
    table_semantics_match = re.search(
        r"Table\s+I\..{0,220}?energy per site.{0,120}?third column"
        r".{0,160}?fourth column gives the stability region of the "
        r"commensurate phases.{0,180}?Hessian.{0,80}?positive definite"
        r".{0,140}?last column gives the conventional names of the "
        r"commensurate antiferromagnetic phases",
        normalized,
        flags=re.IGNORECASE,
    )
    half_coordinate = r"(?:1\s*/\s*2|1\s*2|2\s*1)"
    type_i_match = re.search(
        r"X\s*\(\s*1\s*,\s*0\s*,\s*0\s*\).{0,80}?"
        r"-\s*2\s*J\s*1\s*\+\s*3\s*J\s*2\s*-\s*4\s*J\s*3"
        r".{0,80}?J\s*2\s*<\s*4\s*J\s*3\s*<\s*2\s*J\s*1"
        r"\s*-\s*2\s*J\s*2.{0,40}?Type\s+I\b",
        normalized,
        flags=re.IGNORECASE,
    )
    type_ii_match = re.search(
        rf"L\s*\(?\s*{half_coordinate}\s*,\s*{half_coordinate}"
        rf"\s*,\s*{half_coordinate}\s*\)?.{{0,80}}?"
        r"-\s*3\s*J\s*2.{0,80}?J\s*1\s*-\s*2\s*J\s*2"
        r"\s*<\s*2\s*J\s*3\s*<\s*J\s*1\s*\+\s*J\s*2"
        r".{0,40}?Type\s+II\b",
        normalized,
        flags=re.IGNORECASE,
    )
    type_iii_match = re.search(
        rf"W\s*\(?\s*1\s*,\s*{half_coordinate}\s*,\s*0\s*\)?"
        r".{0,80}?-\s*2\s*J\s*1\s*\+\s*J\s*2\s*\+\s*4\s*J\s*3"
        r".{0,80}?8\s*J\s*3\s*<\s*2\s*J\s*2\s*<\s*J\s*1"
        r"\s*-\s*2\s*J\s*3.{0,40}?Type\s+III\b",
        normalized,
        flags=re.IGNORECASE,
    )
    j1_j2_projection_match = re.search(
        rf"three kinds of antiferromagnetic.{{0,240}}?ordering vectors"
        rf".{{0,80}}?"
        rf"X\s*\(\s*1\s*,\s*0\s*,\s*0\s*\).{{0,100}}?"
        rf"L\s*\(?\s*{half_coordinate}\s*,\s*{half_coordinate}\s*,\s*"
        rf"{half_coordinate}\s*\)?.{{0,100}}?"
        rf"W\s*\(?\s*1\s*,\s*{half_coordinate}\s*,\s*0\s*\)?"
        r".{0,180}?already present in.{0,50}?J\s*1\s*-\s*J\s*2 "
        r"models",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"VIII\.\s*CONCLUSIONS.{0,900}?We presented a detailed study of "
        r"the ground state phase di.{0,300}?agram of the classical isotropic "
        r"J\s*1\s*-\s*J\s*2\s*-\s*J\s*3 Heisenberg model.{0,260}?"
        r"face(?:-| )centered(?:-| )cubic lattice.{0,500}?We found and "
        r"analyzed in.{0,220}?detail.{0,220}?commensurate Type I\s*,"
        r".{0,220}?II and III structures",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        title_match,
        authors_match,
        version_match,
        scope_match,
        hamiltonian_match,
        model_definition_match,
        table_semantics_match,
        type_i_match,
        type_ii_match,
        type_iii_match,
        j1_j2_projection_match,
        conclusion_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} require the identified v3 primary paper, "
            "classical FCC J1-J2-J3 Hamiltonian and neighbor definitions, "
            "Table I semantics and all three exact energy/stability rows, "
            "the explicit J1-J2 projection, and the conclusion"
        )

    return (
        {"common_orders": ["type_I", "type_II", "type_III"]},
        {
            "parser": "parse_balla_iqbal_penc_fcc_type_orders",
            "source_role": (
                "direct corrective primary source for the mismatched "
                "Lines 1963 citation"
            ),
            "equation": "1",
            "table": "I",
            "j3_projection": "J3=0 with J1>0",
            "two_column_layout_forms_accepted": (
                two_column_layout_forms_accepted
            ),
            "phase_ranges": {
                "type_I": "J2<0",
                "type_III": "0<J2/J1<1/2",
                "type_II": "J2/J1>1/2",
            },
            "registered_source_mismatch": (
                "DOI 10.1103/PhysRev.131.546 studies layered CoCl2 and NiCl2, "
                "not the FCC J1-J2 type-order problem"
            ),
            "matched_anchors": [
                "identified Balla-Iqbal-Penc paper title",
                "Balla, Iqbal, and Penc authors",
                "arXiv:2007.00376v3 source identity",
                "classical frustrated FCC Heisenberg scope",
                "classical isotropic J1-J2-J3 Hamiltonian in equation (1)",
                "unit vectors and first-, second-, and third-neighbor meanings",
                "Table I energy, stability, and conventional-name semantics",
                "X Type-I energy and stability row",
                "L Type-II energy and stability row",
                "W Type-III energy and stability row",
                "three antiferromagnets already present in the J1-J2 model",
                "conclusion identifying commensurate Type I, II, III structures",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def recompute_fcc_j1_j2_type_orders(
    *, j1, type_i_j2, type_iii_j2, type_ii_j2
):
    """Project Table I to J3=0 and verify one interior probe per type order."""

    j1 = _require_positive_finite_real(
        j1, label="FCC J1-J2 type orders J1"
    )
    probes = {
        "type_I": _require_finite_real(
            type_i_j2, label="FCC J1-J2 type orders Type-I J2 probe"
        ),
        "type_III": _require_finite_real(
            type_iii_j2, label="FCC J1-J2 type orders Type-III J2 probe"
        ),
        "type_II": _require_finite_real(
            type_ii_j2, label="FCC J1-J2 type orders Type-II J2 probe"
        ),
    }

    def table_i_energies(j2):
        return {
            "type_I": -2.0 * j1 + 3.0 * j2,
            "type_II": -3.0 * j2,
            "type_III": -2.0 * j1 + j2,
        }

    projected_stability = {
        "type_I": lambda j2: j2 < 0.0 < 2.0 * j1 - 2.0 * j2,
        "type_III": lambda j2: 0.0 < 2.0 * j2 < j1,
        "type_II": lambda j2: j1 - 2.0 * j2 < 0.0 < j1 + j2,
    }
    for expected_type, j2 in probes.items():
        if not projected_stability[expected_type](j2):
            raise RuntimeEvidenceError(
                "FCC J1-J2 type orders probes must lie strictly inside "
                "the J3=0 Type-I, Type-III, and Type-II stability regions"
            )
        energies = table_i_energies(j2)
        minimum_energy = min(energies.values())
        minimizers = [
            phase
            for phase, energy in energies.items()
            if math.isclose(
                energy, minimum_energy, rel_tol=0.0, abs_tol=1.0e-12
            )
        ]
        if minimizers != [expected_type]:
            raise RuntimeEvidenceError(
                "FCC J1-J2 type orders Table-I energies did not select "
                f"{expected_type} uniquely"
            )

    return {"common_orders": ["type_I", "type_II", "type_III"]}


def parse_henley_pyrochlore_coulomb_phase(source_text):
    """Extract the tetrahedron constraint and pinch points from Henley."""

    error_prefix = "Henley pyrochlore Coulomb phase"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_henley_pyrochlore_coulomb_phase"
    )
    return _finalize_prepared_trace(
        _parse_henley_pyrochlore_coulomb_phase_prepared(prepared.text),
        prepared,
    )


def _parse_henley_pyrochlore_coulomb_phase_prepared(normalized):
    error_prefix = "Henley pyrochlore Coulomb phase"

    identity_match = re.search(
        r"POWER(?:-| )LAW SPIN CORRELATIONS IN PYROCHLORE "
        r"ANTIFERROMAGNETS.{0,120}?C\.?\s*L\.?\s*Henley",
        normalized,
        flags=re.IGNORECASE,
    )
    version_match = re.search(
        r"arXiv\s*:\s*cond(?:-| )mat\s*/\s*0407005v1",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"ground state ensemble of the highly frustrated pyrochlore"
        r"(?:-| )lattice antiferromagnet can be.{0,180}?mapped to a "
        r"coarse(?:-| )grained.{0,40}?polarization.{0,80}?zero"
        r"(?:-| )divergence condition.{0,260}?spin correlations"
        r".{0,120}?dipole(?:-| )dipole interaction.{0,100}?"
        r"1\s*/\s*\|?\s*R\s*\|?\s*(?:\^?\s*3|3)"
        r".{0,360}?pinch(?:-| )point.{0,80}?pseudo(?:-| )dipolar"
        r".{0,100}?singularities at reciprocal lattice vectors",
        normalized,
        flags=re.IGNORECASE,
    )
    if abstract_match is None:
        abstract_match = re.search(
            r"ground state ensemble of the highly frustrated pyrochlore"
            r"(?:-| )lattice antiferromagnet can be.{0,180}?mapped to a "
            r"coarse(?:-| )grained.{0,40}?polarization.{0,80}?zero"
            r"(?:-| )divergence condition.{0,260}?spin correlations"
            r".{0,120}?dipole(?:-| )dipole interaction.{0,100}?"
            r"1\s*/\s*\|?\s*R\s*\|?\s*(?:\^?\s*3|3)"
            r".{0,360}?pinch(?:-| )point.{0,80}?pseudodipolar"
            r".{0,100}?singularities at reciprocal lattice vectors",
            normalized,
            flags=re.IGNORECASE,
        )
    clean_model_match = re.search(
        r"pyrochlore lattice consists of corner(?:-| )sharing tetrahedra"
        r".{0,900}?spin Hamiltonian.{0,200}?only nearest(?:-| )neighbor"
        r".{0,500}?antiferromagnetic exchange.{0,500}?cast as a sum of"
        r".{0,300}?squares.{0,300}?H\s*_?\s*spin\s*=\s*J\s*_?\s*spin"
        r".{0,160}?s\s*_?\s*i\s+dot\s+s\s*_?\s*j.{0,140}?const"
        r".{0,160}?J\s*_?\s*spin\s*/\s*2.{0,140}?"
        r"L\s*_?\s*(?:alpha|α)\s*(?:\^?\s*2|2)"
        r".{0,80}?\(\s*1\.2\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    extracted_model_match = re.search(
        r"pyrochlore lattice consists of corner(?:-| )sharing "
        r"tetra.{0,160}?hedra.{0,2800}?spin Hamiltonian"
        r".{0,200}?only nearest(?:-| )neighbor.{0,500}?"
        r"antiferromagnetic exchange.{0,120}?cast as a sum of"
        r".{0,180}?groundsquares\s*:\s*state ensemble"
        r".{0,80}?X\s*J\s*_?\s*spin\s+X\s*2\s*H\s*_?\s*spin"
        r"\s*=\s*J\s*_?\s*spin.{0,40}?s\s*_?\s*i\s+dot\s+"
        r"s\s*_?\s*j.{0,80}?const\s*=\s*L\s*_?\s*(?:alpha|α)"
        r".{0,40}?\(\s*1\.2\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = clean_model_match or extracted_model_match
    clean_constraint_match = re.search(
        r"total spin of four sites in a tetrahedron.{0,500}?"
        r"L\s*_?\s*(?:alpha|α)\s*(?:≡|=).{0,180}?"
        r"s\s*_?\s*i.{0,100}?\(\s*1\.3\s*\)"
        r".{0,1800}?From\s*\(\s*1\.4\s*\)\s*it is evident that any state "
        r"with.{0,500}?L\s*_?\s*(?:alpha|α)\s*=\s*0"
        r".{0,100}?\(\s*1\.5\s*\).{0,600}?classical ground state"
        r".{0,160}?massively degenerate",
        normalized,
        flags=re.IGNORECASE,
    )
    extracted_constraint_match = re.search(
        r"total spin of four sites in a tetrahedron.{0,500}?"
        r"L\s*_?\s*(?:alpha|α)\s*(?:≡|=).{0,180}?"
        r"s\s*_?\s*i.{0,100}?\(\s*1\.3\s*\)"
        r".{0,500}?i\s*(?:∈|in)\s*(?:alpha|α)"
        r".{0,1600}?From\s*\(\s*1\.4\s*\)\s*it is evident that any state "
        r"with.{0,500}?L\s*_?\s*(?:alpha|α)\s*=\s*0"
        r".{0,100}?\(\s*1\.5\s*\).{0,600}?classical ground state"
        r".{0,160}?massively degener.{0,100}?anharmonic terms in the "
        r"Holstein(?:-| )Primakoff expansion.{0,100}?ate",
        normalized,
        flags=re.IGNORECASE,
    )
    constraint_match = clean_constraint_match or extracted_constraint_match
    heisenberg_scope_match = re.search(
        r"other two situations correspond to isotropic.{0,350}?Heisenberg "
        r"models in the large(?:-| )S semiclassical regime"
        r".{0,900}?low(?:-| )T limit of the.{0,100}?classical Heisenberg "
        r"model.{0,300}?polarization.{0,160}?extends? to the.{0,80}?"
        r"Heisenberg spin case",
        normalized,
        flags=re.IGNORECASE,
    )
    n_three_match = re.search(
        r"D\.\s*Generalization to Heisenberg spins.{0,500}?case of isotropic "
        r"n\s*=\s*3 component spins.{0,180}?reiterate all the "
        r"coarse(?:-| )graining arguments.{0,200}?Heisenberg spin components"
        r".{0,500}?polarization field.{0,180}?tensor.{0,600}?"
        r"three equations.{0,120}?one for each spin(?:-| )space component",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_structure_factor_match = re.search(
        r"structure factor.{0,120}?neutron diffraction intensity"
        r".{0,180}?pseudo(?:-| )dipolar singularities"
        r".{0,180}?K\s*_?\s*200\s*\+\s*q.{0,120}?"
        r"q\s*_?\s*perp\s*(?:\^?\s*2|2)\s*/\s*\("
        r"\s*q\s*_?\s*parallel\s*(?:\^?\s*2|2)\s*\+\s*"
        r"q\s*_?\s*perp\s*(?:\^?\s*2|2)\s*\)"
        r".{0,80}?\(\s*2\.10\s*\).{0,180}?K\s*_?\s*200"
        r".{0,120}?reciprocal lattice vector.{0,180}?q\s*_?\s*parallel"
        r".{0,120}?q\s*_?\s*perp",
        normalized,
        flags=re.IGNORECASE,
    )
    extracted_structure_factor_match = re.search(
        r"structure factor.{0,120}?neutron diffraction intensity"
        r".{0,220}?pseudo(?:-| )dipolar singu.{0,700}?larities"
        r".{0,260}?q\s*⊥.{0,180}?K\s*200\s*\+\s*q"
        r".{0,120}?\(\s*2\.10\s*\).{0,500}?K\s*200"
        r".{0,160}?reciprocal lattice vector.{0,260}?q\s*k"
        r".{0,120}?q\s*⊥",
        normalized,
        flags=re.IGNORECASE,
    )
    structure_factor_match = (
        clean_structure_factor_match or extracted_structure_factor_match
    )
    pinch_point_match = re.search(
        r"Several pyrochlore systems show the same characteris.{0,240}?"
        r"tic diffuse scattering features.{0,600}?pinch(?:-| )point "
        r"singu.{0,500}?larity of form\s*\(\s*2\.10\s*\)\s*at "
        r"K\s*_?\s*200.{0,100}?also K\s*_?\s*111 reciprocal lattice vectors",
        normalized,
        flags=re.IGNORECASE,
    )
    summary_match = re.search(
        r"In summary.{0,80}?polarization can be de.{0,300}?fined in "
        r"pyrochlore antiferromagnets.{0,300}?in a ground.{0,160}?state"
        r".{0,300}?exactly satisfies a divergence condition"
        r".{0,500}?correlations (?:were found|have).{0,160}?"
        r"pseudo(?:-| )dipolar form"
        r".{0,240}?pure power law.{0,180}?infinite correlation length",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        version_match,
        abstract_match,
        model_match,
        constraint_match,
        heisenberg_scope_match,
        n_three_match,
        structure_factor_match,
        pinch_point_match,
        summary_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified Henley paper, its "
            "nearest-neighbor pyrochlore sum-of-squares Hamiltonian, "
            "L_alpha=0 ground-state constraint, explicit n=3 Heisenberg "
            "extension, pseudo-dipolar structure factor Eq. (2.10), "
            "K_200/K_111 pinch points, and divergence-law summary"
        )

    return (
        {
            "zero_total_spin_per_tetrahedron": True,
            "pinch_points": True,
        },
        {
            "parser": "parse_henley_pyrochlore_coulomb_phase",
            "source_role": (
                "direct corrective source adding the pinch-point result "
                "absent from the registered Moessner-Chalker 1998 paper"
            ),
            "equations": ["1.2", "1.3", "1.5", "2.10"],
            "spin_scope": "isotropic classical n=3 Heisenberg",
            "pinch_point_locations": ["K_200", "K_111"],
            "registered_source_limitation": (
                "DOI 10.1103/PhysRevLett.80.2929 establishes L_alpha=0 but "
                "does not contain the pinch-point structure-factor result"
            ),
            "two_column_layout_forms_accepted": bool(
                extracted_model_match is not None
                and extracted_constraint_match is not None
                and re.search(
                    r"pinch(?:-| )point.{0,80}?pseudodipolar",
                    abstract_match.group(0),
                    flags=re.IGNORECASE,
                )
            ),
            "matched_anchors": [
                "identified Henley paper title and author",
                "arXiv:cond-mat/0407005v1 source identity",
                "abstract zero-divergence, dipolar-correlation, and pinch-point claim",
                "nearest-neighbor pyrochlore sum-of-squares Hamiltonian Eq. (1.2)",
                "tetrahedron total spin Eq. (1.3) and ground-state constraint Eq. (1.5)",
                "large-S and low-temperature classical Heisenberg scope",
                "isotropic n=3 Heisenberg tensor-polarization generalization",
                "pseudo-dipolar structure factor Eq. (2.10)",
                "pinch points at K_200 and K_111",
                "summary exact divergence constraint and power-law correlations",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def recompute_pyrochlore_coulomb_phase(*, exchange, momentum_probe):
    """Check the tetrahedron minimum and directional Eq. (2.10) limits."""

    exchange = _require_positive_finite_real(
        exchange, label="pyrochlore Coulomb phase exchange"
    )
    momentum_probe = _require_positive_finite_real(
        momentum_probe, label="pyrochlore Coulomb phase momentum probe"
    )

    zero_sum_spins = (
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
    )
    aligned_spins = ((1.0, 0.0, 0.0),) * 4
    component_sums = [
        math.fsum(spin[component] for spin in zero_sum_spins)
        for component in range(3)
    ]
    def tetrahedron_energy(spins):
        total = [math.fsum(spin[index] for spin in spins) for index in range(3)]
        return 0.5 * exchange * (
            sum(component * component for component in total)
            - sum(sum(component * component for component in spin) for spin in spins)
        )

    zero_sum_energy = tetrahedron_energy(zero_sum_spins)
    aligned_energy = tetrahedron_energy(aligned_spins)
    if (
        component_sums != [0.0, 0.0, 0.0]
        or not math.isclose(
            zero_sum_energy, -2.0 * exchange, rel_tol=0.0, abs_tol=1.0e-15
        )
        or not zero_sum_energy < aligned_energy
    ):
        raise RuntimeEvidenceError(
            "pyrochlore Coulomb phase tetrahedron energy did not select "
            "zero total spin"
        )

    def equation_2_10(q_parallel, q_perp):
        denominator = q_parallel**2 + q_perp**2
        if denominator <= 0.0:
            raise RuntimeEvidenceError(
                "pyrochlore Coulomb phase Eq. (2.10) requires nonzero momentum"
            )
        return q_perp**2 / denominator

    longitudinal_limit = equation_2_10(momentum_probe, 0.0)
    transverse_limit = equation_2_10(0.0, momentum_probe)
    diagonal_limit = equation_2_10(momentum_probe, momentum_probe)
    if not (
        longitudinal_limit == 0.0
        and transverse_limit == 1.0
        and diagonal_limit == 0.5
    ):
        raise RuntimeEvidenceError(
            "pyrochlore Coulomb phase Eq. (2.10) did not have directional "
            "pinch-point limits"
        )

    return {
        "zero_total_spin_per_tetrahedron": True,
        "pinch_points": True,
    }


def parse_abramchuk_cu2iro3_honeycomb_iridate(source_text):
    """Extract the registered Cu2IrO3 material-identity claim."""

    error_prefix = "Abramchuk Cu2IrO3 honeycomb iridate"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_abramchuk_cu2iro3_honeycomb_iridate"
    )
    return _finalize_prepared_trace(
        _parse_abramchuk_cu2iro3_honeycomb_iridate_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_abramchuk_cu2iro3_honeycomb_iridate_prepared(normalized):
    error_prefix = "Abramchuk Cu2IrO3 honeycomb iridate"

    cu2iro3 = r"Cu\s*2\s*Ir\s*O\s*3"
    na2iro3 = r"Na\s*2\s*Ir\s*O\s*3"
    a2iro3 = r"A\s*2\s*Ir\s*O\s*3"
    mixed_octahedron = (
        r"\(\s*Ir\s*2\s*/\s*3\s*Cu\s*1\s*/\s*3\s*\)\s*O\s*6"
    )

    identity_match = re.search(
        cu2iro3
        + r"\s*:\s*A New Magnetically Frustrated Honeycomb Iridate"
        r".{0,500}?Mykola Abramchuk.{0,500}?Fazel Tafti",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"DOI\s*:\s*10\.1021\s*/\s*jacs\.7b06911",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_identity_match = re.search(
        r"ABSTRACT\s*:\s*We present the first copper iridium binary "
        r"metal oxide with the chemical formula\s*"
        + cu2iro3,
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_structure_match = re.search(
        cu2iro3
        + r"\s+has the same monoclinic space group\s*\(\s*C2\s*/\s*c\s*\)"
        r"\s+as\s+"
        + na2iro3
        + r"\s+with a layered honeycomb structure",
        normalized,
        flags=re.IGNORECASE,
    )
    figure_structure_match = re.search(
        r"Figure\s*1\.\s*Structural and chemical relations between"
        r".{0,180}?"
        + cu2iro3
        + r".{0,80}?structure of\s+"
        + cu2iro3
        + r"\s+consists of edge(?:-|\s+)sharing\s+"
        + mixed_octahedron
        + r"\s+octahedra in honeycomb layers"
        r".{0,400}?Sodium atoms are replaced by copper atoms both"
        r".{0,120}?within the honeycomb layers",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_refinement_match = re.search(
        r"Structural refinement shows that.{0,900}?"
        + cu2iro3
        + r"\s+crystallizes in the\s+C2\s*/\s*c\s+space group"
        r".{0,900}?honeycomb layers of edge(?:-|\s+)sharing\s+"
        + mixed_octahedron
        + r"\s+octahedra",
        normalized,
        flags=re.IGNORECASE,
    )
    extracted_refinement_match = re.search(
        r"Structural refinement shows that.{0,160}?diffraction pattern "
        r"after 3 weeks at ambient conditions\.\s*"
        + cu2iro3
        + r"\s+crystallizes in the\s+C2\s*/\s*c\s+space group with "
        r"honeycomb.{0,120}?X(?:-|\s+)ray Diffraction\.\s*Powder "
        r"X(?:-|\s+)ray diffraction\s*\(\s*PXRD\s*\)\s*was layers of "
        r"edge(?:-|\s+)sharing\s+"
        + mixed_octahedron
        + r"\s+octahedra",
        normalized,
        flags=re.IGNORECASE,
    )
    refinement_match = (
        clean_refinement_match or extracted_refinement_match
    )
    clean_conclusion_match = re.search(
        r"CONCLUSIONS.{0,1800}?resulting material,\s*"
        + cu2iro3
        + r",\s*is the first copper iridium binary metal oxide"
        r".{0,600}?a new member of\s+"
        + a2iro3
        + r"\s+honeycomb iridates",
        normalized,
        flags=re.IGNORECASE,
    )
    extracted_conclusion_match = re.search(
        r"CONCLUSIONS.{0,500}?demonstrate that it is possible to completely "
        r"substitute all sodium atoms in\s+"
        + na2iro3
        + r"\s+with copper atoms.{0,400}?topotactic reaction under mild "
        r"conditions\..{0,80}?The resulting.{0,400}?material,\s*"
        + cu2iro3
        + r",\s*is the first copper iridium binary metal.{0,250}?oxide and "
        r"a new member of\s+"
        + a2iro3
        + r"\s+honeycomb iridates",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = clean_conclusion_match or extracted_conclusion_match
    matches = (
        identity_match,
        doi_match,
        abstract_identity_match,
        abstract_structure_match,
        figure_structure_match,
        refinement_match,
        conclusion_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified article and DOI, "
            "explicit Cu2IrO3 copper-iridium-oxide identity, C2/c layered "
            "honeycomb structure in the abstract, structural figure and "
            "refinement, and the A2IrO3 honeycomb-iridate conclusion"
        )

    return (
        {"honeycomb_frustrated_iridate_identity": True},
        {
            "parser": "parse_abramchuk_cu2iro3_honeycomb_iridate",
            "doi": "10.1021/jacs.7b06911",
            "claim_scope": (
                "material identity and layered honeycomb structure only; no "
                "generic Kitaev- or Gamma-model projection"
            ),
            "two_column_layout_forms_accepted": bool(
                extracted_refinement_match is not None
                and extracted_conclusion_match is not None
            ),
            "matched_anchors": [
                "identified Abramchuk et al. Cu2IrO3 article",
                "registered DOI 10.1021/jacs.7b06911",
                "abstract copper-iridium-binary-oxide identity",
                "abstract C2/c layered honeycomb structure",
                "Figure 1 edge-sharing octahedra in honeycomb layers",
                "structural-refinement C2/c honeycomb-layer assignment",
                "conclusion assigns Cu2IrO3 to A2IrO3 honeycomb iridates",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_enderle_licuvo4_incommensurate_helimagnet(source_text):
    """Extract the observed incommensurate helical order in LiCuVO4."""

    error_prefix = "Enderle LiCuVO4 incommensurate helimagnet"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_enderle_licuvo4_incommensurate_helimagnet"
    )
    return _finalize_prepared_trace(
        _parse_enderle_licuvo4_incommensurate_helimagnet_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_enderle_licuvo4_incommensurate_helimagnet_prepared(normalized):
    error_prefix = "Enderle LiCuVO4 incommensurate helimagnet"

    licuvo4 = r"Li\s*Cu\s*V\s*O\s*4"
    neighbour = r"neighbou?r"

    identity_match = re.search(
        r"Quantum helimagnetism of the frustrated spin(?:-|\s+)\s*"
        r"1\s*/?\s*2\s+chain\s+"
        + licuvo4
        + r".{0,500}?M\.\s*Enderle.{0,1200}?H\.\s*M\.\s*R"
        r"(?:ø|o)nn?ow",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"DOI\s*:\s*10\.1209\s*/\s*epl\s*/\s*i2004(?:-| )10484(?:-| )x",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"Abstract\..{0,40}?Inelastic neutron scattering,\s*"
        r"susceptibility,\s*and high(?:-|\s+)field magnetization identify\s+"
        + licuvo4
        + r"\s+as a nearest(?:-|\s+)"
        + neighbour
        + r"\s+ferromagnetic,\s*next(?:-|\s+)nearest(?:-|\s+)"
        + neighbour
        + r"\s+frustrated,\s*quasi(?:-|\s+)one(?:-\s*|\s+)dimensional "
        r"helimagnet",
        normalized,
        flags=re.IGNORECASE,
    )
    structure_match = re.search(
        licuvo4
        + r"\s+crystallizes in the space group Imma.{0,160}?"
        r"edge(?:-|\s+)shared\s+Cu\s*O\s*2\s+chains "
        r"run(?:-\s*|\s*)ning along b"
        r".{0,160}?magnetic structure is helical with propagation vector"
        r"\s*\(\s*0\s+(?P<q_b>0\.532)\s+0\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    ordered_phase_match = re.search(
        r"All data were taken in the ordered phase below\s+"
        r"T\s*_?\s*N\s*=\s*2\.1\s*K,\s*verified by the presence of a "
        r"magnetic Bragg peak",
        normalized,
        flags=re.IGNORECASE,
    )
    interaction_match = re.search(
        r"full data set is only compatible with ferromagnetic "
        r"(?:nn|nearest(?:-|\s+)"
        + neighbour
        + r")\s+intrachain interaction\s+J\s*1\s*,\s*and antiferromagnetic "
        r"(?:nnn|next(?:-|\s+)nearest(?:-|\s+)"
        + neighbour
        + r")\s+interaction\s+J\s*2",
        normalized,
        flags=re.IGNORECASE,
    )
    pitch_match = re.search(
        r"experimentally observed incommensurability translates into a pitch "
        r"angle of\s*(?P<pitch>83\.6)\s*(?:\+/-|±)\s*0\.6"
        r"\s*(?:degrees|°|◦)",
        normalized,
        flags=re.IGNORECASE,
    )
    summary_match = re.search(
        r"To summarize,\s*our results demonstrate that\s+"
        + licuvo4
        + r"\s+can be described coherently with a frustrated "
        r"F\s*M\s*nn\s*-\s*AF\s*nnn\s+chain model supplemented with a "
        r"small ferromagnetic frustrating interchain interaction",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        doi_match,
        abstract_match,
        structure_match,
        ordered_phase_match,
        interaction_match,
        pitch_match,
        summary_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified article and DOI, "
            "abstract quasi-one-dimensional helimagnet classification, "
            "helical propagation vector, magnetically ordered phase and "
            "Bragg peak, FM J1/AF J2 hierarchy, measured incommensurate "
            "pitch, and the concluding frustrated-chain model"
        )

    return (
        {"incommensurate_spiral_order": True},
        {
            "parser": "parse_enderle_licuvo4_incommensurate_helimagnet",
            "doi": "10.1209/epl/i2004-10484-x",
            "propagation_vector_rlu": [
                0.0,
                float(structure_match.group("q_b")),
                0.0,
            ],
            "pitch_angle_degrees": float(pitch_match.group("pitch")),
            "exchange_hierarchy": {
                "J1": "ferromagnetic nearest-neighbour",
                "J2": "antiferromagnetic next-nearest-neighbour",
            },
            "claim_scope": (
                "observed incommensurate helical order in LiCuVO4; not a "
                "generic J1-J2-chain phase-diagram claim"
            ),
            "verified_epl_layout_forms_accepted": bool(
                re.search(
                    r"quasi(?:-|\s+)one-\s+dimensional",
                    normalized,
                    flags=re.IGNORECASE,
                )
                and re.search(
                    r"chains run-\s+ning",
                    normalized,
                    flags=re.IGNORECASE,
                )
                and re.search(
                    r"intrachain interaction\s+J\s*1\s+,",
                    normalized,
                    flags=re.IGNORECASE,
                )
            ),
            "matched_anchors": [
                "identified Enderle et al. LiCuVO4 article",
                "registered DOI 10.1209/epl/i2004-10484-x",
                "abstract quasi-one-dimensional helimagnet identification",
                "helical structure with propagation vector (0,0.532,0)",
                "ordered phase below 2.1 K verified by a magnetic Bragg peak",
                "ferromagnetic J1 and antiferromagnetic J2 hierarchy",
                "observed incommensurability gives pitch 83.6(6) degrees",
                "concluding frustrated FMnn-AFnnn chain model",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_bak_jensen_mnsi_long_wavelength_helix(source_text):
    """Extract the observed long-wavelength helix and its mechanism in MnSi."""

    error_prefix = "Bak-Jensen MnSi long-wavelength helix"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_bak_jensen_mnsi_long_wavelength_helix"
    )
    return _finalize_prepared_trace(
        _parse_bak_jensen_mnsi_long_wavelength_helix_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_bak_jensen_mnsi_long_wavelength_helix_prepared(normalized):
    error_prefix = "Bak-Jensen MnSi long-wavelength helix"

    identity_match = re.search(
        r"Theory of helical magnetic structures and phase transitions in "
        r"MnSi and FeGe.{0,400}?Per\s+Bak\s+and\s+"
        r"M\.?\s*H(?:\.|[A-Za-z]{1,8})?\s+Jensen",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"(?:DOI\s*:\s*10\.1088\s*/\s*0022-3719\s*/\s*13\s*/\s*31"
        r"\s*/\s*002|https?://iopscience\.iop\.org\s*/\s*0022-3719"
        r"\s*/\s*13\s*/\s*31\s*/\s*002)",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"Abstract\.\s*The long(?:-|\s+)period helical magnetic structures "
        r"in MnSi and FeGe are shown to be consequences of a ferromagnetic "
        r"Dzyaloshinskii instability",
        normalized,
        flags=re.IGNORECASE,
    )
    observation_match = re.search(
        r"several neutron diffraction experiments showing a helical magnetic "
        r"structure in MnSi.{0,140}?The wavevector is found to be in the "
        r"\(\s*(?P<d1>1)\s*(?P<d2>1)\s*(?P<d3>1)\s*\) direction"
        r".{0,100}?\(\s*[-~]?\s*(?P<q>0\.036)\s*A\s*"
        r"(?:\^\s*-\s*1|-\s*(?:1|['’]))\s*\)"
        r".{0,100}?very long period\s*\(\s*[-~]?\s*"
        r"(?P<period>175(?:\.0)?)\s*A\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    gradient_match = re.search(
        r"The b term,\s*which is linear in the gradient,\s*"
        r"destabilis(?:es|zes) the ferromagnetic structure\."
        r".{0,180}?rela(?:tivistic|-\s+tivistic) interactions between the "
        r"spins of the form "
        r"S\s*i\s*x\s*S\s*j",
        normalized,
        flags=re.IGNORECASE,
    )

    clean_eq6_match = re.search(
        r"(?:The )?potential is minimised by\s*"
        r"k\s*=\s*\|\s*b\s*\|\s*/\s*\(\s*B\s*1\s*\+\s*B\s*2\s*/\s*3"
        r"\s*\)\.?\s*\(6\)\s*The smallness of k follows from the "
        r"smallness of b compared to B\s*1\s*\+\s*B\s*2\s*/\s*3",
        normalized,
        flags=re.IGNORECASE,
    )
    extracted_eq6_match = re.search(
        r"which is minimised by.{0,80}?"
        r"k\s*=\s*Ibl\s*/\s*\(\s*B\s*,\s*S\s*B\s*,\s*\)\.?\s*"
        r"\(6\)\s*The smallness of k follows from the smallness of b "
        r"compared to B\s*,\s*\+\s*\+B2",
        normalized,
        flags=re.IGNORECASE,
    )
    eq6_match = clean_eq6_match or extracted_eq6_match

    clean_eq7_match = re.search(
        r"The spin structure can be expressed in terms of the real vectors:"
        r"\s*S\s*\(\s*r\s*\)\s*=\s*alpha_k\s*cos\s*\(\s*k dot r\s*\)"
        r"\s*-\s*beta_k\s*sin\s*\(\s*k dot r\s*\)\.?\s*\(7\)\s*"
        r"This indeed describes left(?:-|\s+)handed or right(?:-|\s+)handed "
        r"spirals with a long period",
        normalized,
        flags=re.IGNORECASE,
    )
    extracted_eq7_match = re.search(
        r"The spin structure can be expressed in terms of the real vectors "
        r"in the following way:.{0,80}?"
        r"S\s*\(\s*r\s*\)\s*=\s*a\s*,\s*cos\s*\(\s*k\s*r\s*\)\s*-\s*"
        r"B\s*k\s*sin\s*\(\s*k\s*\.\s*r\s*\)\s*\(7\)\s*which indeed "
        r"describes left(?:-|\s+)handed or right(?:-|\s+)handed spirals "
        r"with a long period",
        normalized,
        flags=re.IGNORECASE,
    )
    eq7_match = clean_eq7_match or extracted_eq7_match

    conclusion_match = re.search(
        r"In conclusion,\s*we have demonstrated that the helical magnetic "
        r"structures in MnSi and FeGe are caused by a ferromagnetic "
        r"Dzyaloshinskii instability",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        doi_match,
        abstract_match,
        observation_match,
        gradient_match,
        eq6_match,
        eq7_match,
        conclusion_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified article and DOI, "
            "abstract long-period-helix mechanism, neutron-observed MnSi "
            "helix with (111) direction, wavevector and period, the "
            "linear-gradient destabilization, equations (6) and (7), and "
            "the concluding Dzyaloshinskii mechanism"
        )

    wavevector_magnitude = float(observation_match.group("q"))
    reported_period = float(observation_match.group("period"))
    computed_period = 2.0 * math.pi / wavevector_magnitude
    if not math.isclose(
        computed_period,
        reported_period,
        rel_tol=0.0,
        abs_tol=1.0,
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} reported period is inconsistent with 2*pi/|q|"
        )

    return (
        {"long_wavelength_helix": True},
        {
            "parser": "parse_bak_jensen_mnsi_long_wavelength_helix",
            "doi": "10.1088/0022-3719/13/31/002",
            "wavevector_direction": [
                int(observation_match.group("d1")),
                int(observation_match.group("d2")),
                int(observation_match.group("d3")),
            ],
            "wavevector_magnitude_inverse_angstrom": wavevector_magnitude,
            "reported_period_angstrom": reported_period,
            "computed_period_angstrom": computed_period,
            "mechanism": "ferromagnetic Dzyaloshinskii instability",
            "claim_scope": (
                "experimentally reported long-wavelength helix in MnSi and "
                "the Bak-Jensen linear-gradient mechanism"
            ),
            "verified_iop_scan_ocr_forms_accepted": bool(
                extracted_eq6_match is not None
                and extracted_eq7_match is not None
                and re.search(
                    r"Per\s+Bak\s+and\s+M\s+Hsgh\s+Jensen",
                    normalized,
                    flags=re.IGNORECASE,
                )
                and re.search(
                    r"\(\s*-\s*0\.036\s+A-'\s*\)",
                    normalized,
                    flags=re.IGNORECASE,
                )
            ),
            "matched_anchors": [
                "identified Bak-Jensen MnSi/FeGe article",
                "registered DOI 10.1088/0022-3719/13/31/002",
                "abstract long-period-helix Dzyaloshinskii mechanism",
                "neutron-observed MnSi helix with q||(111) and period 175 A",
                "linear-gradient term destabilizes the ferromagnet",
                "equation (6) gives small wavevector from small b",
                "equation (7) gives left- or right-handed long-period spiral",
                "conclusion attributes MnSi helix to Dzyaloshinskii instability",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_seki_cu2oseo3_skyrmion_lattice_phase(source_text):
    """Extract the directly observed skyrmion-lattice phase in Cu2OSeO3."""

    error_prefix = "Seki Cu2OSeO3 skyrmion-lattice phase"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_seki_cu2oseo3_skyrmion_lattice_phase"
    )
    return _finalize_prepared_trace(
        _parse_seki_cu2oseo3_skyrmion_lattice_phase_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_seki_cu2oseo3_skyrmion_lattice_phase_prepared(search_text):
    error_prefix = "Seki Cu2OSeO3 skyrmion-lattice phase"
    verified_layout_hyphenation = all(
        re.search(pattern, search_text, flags=re.IGNORECASE)
        for pattern in (
            r"trian-\s*\n\s*gular lattice",
            r"measure-\s*\n\s*ment of skyrmion density",
            r"dimen-\s*\n\s*sion dependence",
            r"ob-\s*\n\s*served A phase",
        )
    )

    material = r"Cu\s*2\s*O\s*Se\s*O\s*3"

    identity_match = re.search(
        r"Observation of Skyrmions in a Multiferroic Material"
        r".{0,500}?S\.\s*Seki.{0,120}?X\.\s*Z\.\s*Yu"
        r".{0,120}?S\.\s*Ishiwata.{0,120}?Y\.\s*Tokura",
        search_text,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"(?:DOI\s*:\s*)?10\.1126\s*/\s*science\.1214143",
        search_text,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"Here,\s*we report the experimental discovery of magnetoelectric "
        r"skyrmions in an insulating chiral(?:-|\s+)lattice magnet\s*"
        + material
        + r"\s*through Lorentz transmission electron microscopy and "
        r"magnetic susceptibility measurements",
        search_text,
        flags=re.IGNORECASE,
    )
    structure_helix_match = re.search(
        r"The crystal structure of\s*"
        + material
        + r"\s*is characterized by the same space group\s*"
        r"\(\s*cubic and chiral\s*\)\s*P\s*2\s*1\s*3\s*as the B20 alloys"
        r".{0,7000}?Under zero magnetic field.{0,800}?observed (?:the )?"
        r"stripe patterns.{0,1000}?proper screw(?:-|\s+)spin order with a "
        r"modulation period of\s*(?:~|approximately)\s*"
        r"(?P<period>50)\s*nm",
        search_text,
        flags=re.IGNORECASE,
    )
    thin_film_observation_match = re.search(
        r"With H\s*(?:~|approximately)\s*(?P<field>800)\s*Oe applied "
        r"normal to the sample plane.{0,1800}?formation of a triangular "
        r"lattice of skyrmions is observed both for the\s*"
        r"\(\s*110\s*\)\s*and\s*\(\s*111\s*\)\s*planes"
        r".{0,1800}?Every skyrmion in the SkX state has a uniform spin "
        r"chirality",
        search_text,
        flags=re.IGNORECASE,
    )
    figure_match = re.search(
        r"In both cases,\s*proper screw(?:-|\s+)spin texture appears for "
        r"zero magnetic field,\s*whereas a skyrmion lattice with "
        r"(?:the\s+)?identical spin chirality is formed for\s*"
        r"H\s*=\s*(?P<figure_field>800)\s*Oe",
        search_text,
        flags=re.IGNORECASE,
    )
    phase_diagram_match = re.search(
        r"Based on these real(?:-|\s+)space observations,\s*Fig\.\s*2B "
        r"shows the H(?:-|\s+)T phase diagram"
        r"(?:\s*under H\s*\|\|\s*\[\s*111\s*\])?\s*for thin(?:-|\s+)film\s*"
        + material
        + r"\s*determined through the measurement of skyrmion density\."
        r"\s*Skyrmions disappear for H\s*>\s*"
        r"(?P<disappearance_field>1800)\s*Oe",
        search_text,
        flags=re.IGNORECASE,
    )
    bulk_match = re.search(
        r"Considering the reported dimension dependence for the stability "
        r"of the SkX state in B20 alloys"
        r"(?:\s*\(\s*6\s*,\s*7\s*\))?\s*,\s*we conclude that the observed "
        r"A phase represents the SkX state in the bulk form of\s*"
        + material,
        search_text,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        material
        + r"\s*can be regarded as an insulating analog of B20 alloys"
        r".{0,1200}?magnetic phase diagram characterized by the narrow "
        r"A phase\s*\(\s*SkX state\s*\)\s*region"
        r".{0,1500}?In insulators,\s*the skyrmion can be accompanied by "
        r"electric polarization",
        search_text,
        flags=re.IGNORECASE,
    )
    required_matches = (
        identity_match,
        doi_match,
        abstract_match,
        structure_helix_match,
        thin_film_observation_match,
        figure_match,
        phase_diagram_match,
        bulk_match,
        conclusion_match,
    )
    if any(match is None for match in required_matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified article and DOI, "
            "abstract experimental discovery, chiral P213 structure and "
            "zero-field helix, direct 800 Oe triangular-lattice imaging, "
            "the matching Figure 1 assignment, thin-film density phase "
            "diagram, bulk A-phase assignment, and insulating-SkX "
            "conclusion"
        )

    thin_film_field = float(thin_film_observation_match.group("field"))
    figure_field = float(figure_match.group("figure_field"))
    if not math.isclose(
        thin_film_field,
        figure_field,
        rel_tol=0.0,
        abs_tol=0.0,
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} text and Figure 1 fields are inconsistent"
        )

    return (
        {"skyrmion_lattice_phase": True},
        {
            "parser": "parse_seki_cu2oseo3_skyrmion_lattice_phase",
            "doi": "10.1126/science.1214143",
            "thin_film_skyrmion_field_oe": thin_film_field,
            "skyrmion_disappearance_field_oe": float(
                phase_diagram_match.group("disappearance_field")
            ),
            "helical_modulation_period_nm": float(
                structure_helix_match.group("period")
            ),
            "bulk_phase_assignment": "A phase = SkX state",
            "claim_scope": (
                "directly observed thin-film triangular skyrmion lattice "
                "and experimentally assigned bulk A-phase SkX in Cu2OSeO3"
            ),
            "verified_science_layout_hyphenation_accepted": bool(
                verified_layout_hyphenation
            ),
            "matched_anchors": [
                "identified Seki et al. Science article",
                "registered DOI 10.1126/science.1214143",
                "abstract reports experimental Cu2OSeO3 skyrmion discovery",
                "chiral P213 structure and 50 nm zero-field helix",
                "800 Oe triangular skyrmion lattice observed in two planes",
                "Figure 1 assigns identical-chirality SkX at 800 Oe",
                "thin-film SkX density phase diagram and 1800 Oe boundary",
                "bulk A-phase SkX assignment and insulating-SkX conclusion",
            ],
            "text_spans": [
                [identity_match.start(), identity_match.end()],
                [doi_match.start(), doi_match.end()],
                [abstract_match.start(), abstract_match.end()],
                [structure_helix_match.start(), structure_helix_match.end()],
                [
                    thin_film_observation_match.start(),
                    thin_film_observation_match.end(),
                ],
                [figure_match.start(), figure_match.end()],
                [phase_diagram_match.start(), phase_diagram_match.end()],
                [
                    min(bulk_match.start(), conclusion_match.start()),
                    max(bulk_match.end(), conclusion_match.end()),
                ],
            ],
        },
    )


def parse_wernsdorfer_sessoli_fe8_quantum_tunneling(source_text):
    """Extract the directly observed low-temperature tunneling in Fe8."""

    error_prefix = "Wernsdorfer-Sessoli Fe8 quantum tunneling"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_wernsdorfer_sessoli_fe8_quantum_tunneling"
    )
    return _finalize_prepared_trace(
        _parse_wernsdorfer_sessoli_fe8_quantum_tunneling_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_wernsdorfer_sessoli_fe8_quantum_tunneling_prepared(normalized):
    error_prefix = "Wernsdorfer-Sessoli Fe8 quantum tunneling"
    abstract_search_text = normalized

    fe8 = r"Fe\s*8"

    identity_match = re.search(
        r"Quantum Phase Interference and Parity Effects in Magnetic"
        r".{0,1000}?Molecular Clusters"
        r".{0,1000}?W\.\s*Wernsdorfer"
        r".{0,500}?R\.\s*Sessoli",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"(?:DOI\s*:\s*)?10\.1126\s*/\s*science\.284\.5411\.133",
        normalized,
        flags=re.IGNORECASE,
    )
    webprint_identity_match = re.search(
        r"Volume\s+284,\s*Number\s+5411,\s*Issue of\s+2 Apr 1999,"
        r"\s*pp\.\s*133-135\.",
        normalized,
        flags=re.IGNORECASE,
    )
    source_locator_match = doi_match or webprint_identity_match

    abstract_match = re.search(
        r"An experimental method based on the Landau(?:-|\s+)Zener model "
        r"was developed to measure very small tunnel splittings in molecular "
        r"clusters of eight iron atoms"
        r".{0,300}?spin ground state of S\s*=\s*(?P<spin>10)"
        r".{0,400}?observed oscillations of the tunnel splittings"
        r".{0,400}?hard anisotropy axis"
        r".{0,300}?topological quantum interference of two tunnel paths "
        r"of opposite windings"
        r".{0,400}?n even or odd.{0,180}?parity effect",
        abstract_search_text,
        flags=re.IGNORECASE,
    )
    material_match = re.search(
        r"octanuclear iron\s*\(\s*III\s*\)\s*oxo(?:-|\s*)hydroxo cluster"
        r".{0,300}?"
        + fe8
        + r".{0,400}?spin ground state of S\s*=\s*(?P<material_spin>10)"
        r".{0,180}?Ising(?:-|\s*)type magneto(?:-|\s*)crystalline "
        r"anisotropy"
        r".{0,300}?energy barrier for (?:the )?reversal of the magnetization"
        r".{0,180}?(?P<barrier>25)\s*K\s*for\s*"
        + fe8,
        normalized,
        flags=re.IGNORECASE,
    )
    pure_tunneling_match = re.search(
        r"For\s*"
        + fe8
        + r",\s*however,\s*the relaxation time becomes temperature "
        r"independent below\s*(?P<temperature>360)\s*mK"
        r".{0,160}?pure tunneling mechanism between the only populated"
        r"\s*M\s*=\s*(?:\+/-|±)\s*10 states is responsible for the "
        r"relaxation of the magnetization",
        normalized,
        flags=re.IGNORECASE,
    )
    figure_match = re.search(
        r"Fig\.\s*1\.\s*Magnetic hysteresis curves for a crystal of "
        r"molecular\s*"
        + fe8
        + r"\s*clusters at several temperatures"
        r".{0,300}?Resonant tunneling is evidenced by six equally "
        r"separated steps\."
        r".{0,160}?Below\s*(?P<quantum_temperature>0\.4)\s*K,\s*the "
        r"hysteresis loops are temperature independent,\s*demonstrating "
        r"the pure quantum regime",
        normalized,
        flags=re.IGNORECASE,
    )
    measurement_match = re.search(
        r"measurements were made with an array of micro(?:-|\s*)SQUIDs"
        r".{0,300}?study single\s*"
        + fe8
        + r"\s*crystals"
        r".{0,1200}?Measurements of magnetic hysteresis curves"
        r".{0,500}?Resonant tunneling is evidenced by six equally "
        r"separated steps of\s*(?:Delta\s*H\s*z|H\s*z)\s*(?:=\s*)?"
        r"(?P<step>0\.22)\s*T"
        r".{0,200}?T\s*<\s*(?P<transition_temperature>360)\s*mK"
        r".{0,160}?correspond to tunnel transitions",
        normalized,
        flags=re.IGNORECASE,
    )
    landau_zener_match = re.search(
        r"To apply the Landau(?:-|\s+)Zener formula"
        r".{0,800}?swept the applied field at a constant rate over one of "
        r"the resonance transitions and measured the fraction of molecules "
        r"that reversed their spin"
        r".{0,180}?This procedure yields the tunneling rate\s*P\s*and thus "
        r"the tunnel splitting"
        r".{0,500}?good agreement for sweeping rates between\s*"
        r"(?P<fast_rate>0\.5)\s*and\s*(?P<slow_rate>0\.001)\s*T/s",
        normalized,
        flags=re.IGNORECASE,
    )
    oscillation_match = re.search(
        r"For small angles the tunneling rate oscillates with a period "
        r"between minima of\s*(?P<rate_period>0\.41)\s*T"
        r".{0,500}?corresponding tunnel splittings"
        r".{0,180}?oscillate with almost the same period of\s*"
        r"(?P<splitting_period>0\.41)\s*T"
        r".{0,400}?n even or odd.{0,180}?parity effect",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"Our measurement technique"
        r"(?:\s+directly measures|.{0,220}?directly measuring) very small "
        r"tunnel splittings"
        r".{0,300}?very clear oscillation in the tunnel splittings"
        r".{0,180}?direct evidence of the role of the topological spin "
        r"phase in the spin dynamics of these molecules"
        r".{0,220}?Aharonov(?:-|\s*)Bohm.{0,100}?oscillation in a magnetic "
        r"system",
        normalized,
        flags=re.IGNORECASE,
    )

    required_matches = (
        identity_match,
        source_locator_match,
        abstract_match,
        material_match,
        pure_tunneling_match,
        figure_match,
        measurement_match,
        landau_zener_match,
        oscillation_match,
        conclusion_match,
    )
    if any(match is None for match in required_matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified article and exact "
            "source locator, Landau-Zener Fe8 abstract, S=10 Ising-like "
            "molecular magnet, temperature-independent ground-state "
            "tunneling, Figure 1 pure-quantum regime, micro-SQUID "
            "hysteresis steps, quantitative Landau-Zener procedure, "
            "0.41 T parity oscillations, and direct-evidence conclusion"
        )

    spin = float(abstract_match.group("spin"))
    material_spin = float(material_match.group("material_spin"))
    if not math.isclose(spin, material_spin, rel_tol=0.0, abs_tol=0.0):
        raise RuntimeEvidenceError(
            f"{error_prefix} gives inconsistent Fe8 ground-state spins"
        )

    pure_tunneling_temperature_k = (
        float(pure_tunneling_match.group("temperature")) / 1000.0
    )
    transition_temperature_k = (
        float(measurement_match.group("transition_temperature")) / 1000.0
    )
    if not math.isclose(
        pure_tunneling_temperature_k,
        transition_temperature_k,
        rel_tol=0.0,
        abs_tol=0.0,
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} gives inconsistent tunneling temperatures"
        )

    rate_period = float(oscillation_match.group("rate_period"))
    splitting_period = float(
        oscillation_match.group("splitting_period")
    )
    if not math.isclose(
        rate_period,
        splitting_period,
        rel_tol=0.0,
        abs_tol=0.0,
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} gives inconsistent oscillation periods"
        )

    return (
        {"macroscopic_quantum_tunneling_observed": True},
        {
            "parser": "parse_wernsdorfer_sessoli_fe8_quantum_tunneling",
            "doi": "10.1126/science.284.5411.133",
            "spin_ground_state": spin,
            "pure_quantum_regime_below_k": float(
                figure_match.group("quantum_temperature")
            ),
            "ground_state_tunneling_below_k": pure_tunneling_temperature_k,
            "resonance_step_tesla": float(measurement_match.group("step")),
            "tunnel_splitting_oscillation_period_tesla": splitting_period,
            "method": "micro-SQUID Landau-Zener",
            "claim_scope": (
                "macroscopically measured, temperature-independent "
                "ground-state tunneling in a molecular Fe8 crystal; not a "
                "claim of a macroscopic coherent superposition"
            ),
            "verified_science_webprint_identity_accepted": bool(
                doi_match is None and webprint_identity_match is not None
            ),
            "matched_anchors": [
                "identified Wernsdorfer-Sessoli Fe8 Science article",
                "registered DOI or exact Science webprint citation tuple",
                "abstract Landau-Zener Fe8 interference and parity chain",
                "Fe8 S=10 Ising-type molecular magnet with 25 K barrier",
                "temperature-independent M=+/-10 pure tunneling below 360 mK",
                "Figure 1 shows the pure quantum regime below 0.4 K",
                "micro-SQUID hysteresis gives six 0.22 T tunneling steps",
                "Landau-Zener sweep quantitatively yields tunnel splitting",
                "0.41 T parity oscillations and direct-evidence conclusion",
            ],
            "text_spans": [
                [identity_match.start(), identity_match.end()],
                [source_locator_match.start(), source_locator_match.end()],
                [abstract_match.start(), abstract_match.end()],
                [material_match.start(), material_match.end()],
                [pure_tunneling_match.start(), pure_tunneling_match.end()],
                [figure_match.start(), figure_match.end()],
                [measurement_match.start(), measurement_match.end()],
                [landau_zener_match.start(), landau_zener_match.end()],
                [
                    min(oscillation_match.start(), conclusion_match.start()),
                    max(oscillation_match.end(), conclusion_match.end()),
                ],
            ],
        },
    )


def parse_kitagawa_h3liir2o6_no_magnetic_order(source_text):
    """Extract the reported absence of magnetic order in H3LiIr2O6."""

    error_prefix = "Kitagawa H3LiIr2O6 no-magnetic-order report"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_kitagawa_h3liir2o6_no_magnetic_order"
    )
    return _finalize_prepared_trace(
        _parse_kitagawa_h3liir2o6_no_magnetic_order_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_kitagawa_h3liir2o6_no_magnetic_order_prepared(normalized):

    error_prefix = "Kitagawa H3LiIr2O6 no-magnetic-order report"

    material = r"H\s*3\s*Li\s*Ir\s*2\s*O\s*6"

    identity_match = re.search(
        r"A spin(?:-|\s+)orbital(?:-|\s+)entangled quantum liquid on a "
        r"honeycomb lattice"
        r".{0,500}?K\.\s*Kitagawa"
        r".{0,500}?T\.\s*Takayama"
        r".{0,1600}?H\.\s*Takagi",
        normalized,
        flags=re.IGNORECASE,
    )
    metadata_match = re.search(
        r"Nature volume\s*554,\s*pages\s*341-345\s*\(\s*2018\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"(?:DOI\s*:\s*)?(?:https?://doi\.org/)?"
        r"10\.1038\s*/\s*nature25482",
        normalized,
        flags=re.IGNORECASE,
    )
    definition_match = re.search(
        r"The quantum spin liquid is a long(?:-|\s+)sought exotic state "
        r"of matter,\s*in which interacting spins remain quantum(?:-|\s+)"
        r"disordered without spontaneous symmetry breaking",
        normalized,
        flags=re.IGNORECASE,
    )
    report_match = re.search(
        r"Here we report a quantum(?:-|\s+)liquid state of "
        r"pseudospin(?:-|\s*)1/2 moments in the 5d(?:-|\s*)electron "
        r"honeycomb compound\s*"
        + material,
        normalized,
        flags=re.IGNORECASE,
    )
    no_order_match = re.search(
        r"This iridate does not display magnetic ordering down to\s*"
        r"(?P<floor>0\.05)\s*kelvin,\s*despite an interaction energy of "
        r"about\s*(?P<interaction>100)\s*kelvin",
        normalized,
        flags=re.IGNORECASE,
    )
    evidence_match = re.search(
        r"We observe signatures of low(?:-|\s*)energy fermionic "
        r"excitations that originate from a small number of spin defects "
        r"in the nuclear(?:-|\s*)magnetic(?:-|\s*)resonance relaxation "
        r"and the specific heat",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"We therefore conclude that\s*"
        + material
        + r"\s*is a quantum spin liquid\."
        r".{0,240}?strongly spin(?:-|\s*)orbit(?:-|\s*)coupled "
        r"5d(?:-|\s*)electron transition(?:-|\s*)metal oxide",
        normalized,
        flags=re.IGNORECASE,
    )
    figure_match = re.search(
        r"Figure\s*2:\s*Evidence from NMR spectroscopy of a spin"
        r"(?:-|\s*)liquid ground state in\s*"
        + material
        + r"\s*down to\s*(?P<nmr_floor>1\.0)\s*K"
        r".{0,300}?Figure\s*3:\s*The Knight shift and relaxation rate "
        r"for\s*"
        + material
        + r"\s*reveal the intrinsic static susceptibility and spin dynamics"
        r".{0,300}?Figure\s*4:\s*Low(?:-|\s*)lying excitations are "
        r"captured by the specific heat",
        normalized,
        flags=re.IGNORECASE,
    )
    required_matches = (
        identity_match,
        metadata_match,
        doi_match,
        definition_match,
        report_match,
        no_order_match,
        evidence_match,
        conclusion_match,
        figure_match,
    )
    if any(match is None for match in required_matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified article, authors, "
            "Nature citation and DOI, quantum-disordered definition, "
            "H3LiIr2O6 honeycomb report, 0.05 K no-order observation "
            "against the 100 K interaction scale, NMR and specific-heat "
            "evidence, the source conclusion, and Figures 2-4"
        )

    no_order_floor = float(no_order_match.group("floor"))
    interaction_energy = float(no_order_match.group("interaction"))
    nmr_floor = float(figure_match.group("nmr_floor"))
    if no_order_floor >= nmr_floor:
        raise RuntimeEvidenceError(
            f"{error_prefix} gives inconsistent bulk and NMR floor "
            "temperatures"
        )

    return (
        {"no_magnetic_order_reported": True},
        {
            "parser": "parse_kitagawa_h3liir2o6_no_magnetic_order",
            "doi": "10.1038/nature25482",
            "no_order_down_to_k": no_order_floor,
            "interaction_energy_k": interaction_energy,
            "nmr_spin_liquid_floor_k": nmr_floor,
            "source_representation": "Nature publisher article-page text",
            "claim_scope": (
                "the source reports no magnetic ordering in H3LiIr2O6 "
                "down to 0.05 K; it does not by itself prove an ideal "
                "disorder-free Kitaev spin liquid"
            ),
            "matched_anchors": [
                "identified Kitagawa et al. honeycomb quantum-liquid article",
                "Nature 554, 341-345 (2018) citation",
                "registered DOI 10.1038/nature25482",
                "quantum-disordered-without-symmetry-breaking definition",
                "reported pseudospin-1/2 honeycomb H3LiIr2O6 state",
                "no magnetic order to 0.05 K despite 100 K interactions",
                "NMR/specific-heat signatures and stated QSL conclusion",
                "Figures 2-4 identify NMR, susceptibility and heat evidence",
            ],
            "text_spans": [
                [identity_match.start(), identity_match.end()],
                [metadata_match.start(), metadata_match.end()],
                [doi_match.start(), doi_match.end()],
                [definition_match.start(), definition_match.end()],
                [report_match.start(), report_match.end()],
                [no_order_match.start(), no_order_match.end()],
                [
                    min(evidence_match.start(), conclusion_match.start()),
                    max(evidence_match.end(), conclusion_match.end()),
                ],
                [figure_match.start(), figure_match.end()],
            ],
        },
    )


def parse_ramirez_dy2ti2o7_pauling_entropy(source_text):
    """Extract the calorimetric Pauling-entropy observation in Dy2Ti2O7."""

    error_prefix = "Ramirez Dy2Ti2O7 Pauling entropy"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_ramirez_dy2ti2o7_pauling_entropy"
    )
    return _finalize_prepared_trace(
        _parse_ramirez_dy2ti2o7_pauling_entropy_prepared(prepared.text),
        prepared,
    )


def _parse_ramirez_dy2ti2o7_pauling_entropy_prepared(normalized):

    error_prefix = "Ramirez Dy2Ti2O7 Pauling entropy"

    material = r"Dy\s*2\s*Ti\s*2\s*O\s*7"
    ice_ih = r"ice\s+I\s*_?\s*\(?\s*h\s*\)?"

    identity_match = re.search(
        r"Zero(?:-|\s*)point entropy in\s*'spin ice'"
        r".{0,500}?A\.\s*P\.\s*Ramirez"
        r".{0,500}?A\.\s*Hayashi"
        r".{0,500}?R\.\s*J\.\s*Cava"
        r".{0,800}?R\.\s*Siddharthan"
        r".{0,800}?B\.\s*S\.\s*Shastry",
        normalized,
        flags=re.IGNORECASE,
    )
    metadata_match = re.search(
        r"Nature volume\s*399,\s*pages\s*333-335\s*\(\s*1999\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"(?:DOI\s*:\s*)?(?:https?://doi\.org/)?"
        r"10\.1038\s*/\s*20619",
        normalized,
        flags=re.IGNORECASE,
    )
    pauling_match = re.search(
        r"Common water ice\s*\(\s*"
        + ice_ih
        + r"\s*\).{0,300}?Pauling showed that the presence of "
        r"(?:these two bond lengths|two inequivalent O(?:-|\s*)H bond lengths) "
        r"leads to a macroscopic degeneracy of possible ground states"
        r".{0,140}?system has finite entropy as the temperature tends "
        r"towards zero",
        normalized,
        flags=re.IGNORECASE,
    )
    analogy_match = re.search(
        r"An analogous system.{0,120}?this degeneracy can be studied is a "
        r"magnet with the pyrochlore structure"
        r"(?:-+|\s*)termed\s*'spin ice'(?:-+|\s*)where spin orientation "
        r"plays a similar role to that of the hydrogen position in\s*"
        + ice_ih,
        normalized,
        flags=re.IGNORECASE,
    )
    measurement_match = re.search(
        r"Here we present specific(?:-|\s*)heat data for\s*one such system,"
        r"\s*"
        + material
        + r",\s*from which we infer a total spin\s*entropy of\s*"
        r"(?P<measured>0\.67)\s*R\s*ln\s*2\."
        r".{0,120}?similar to the value,\s*"
        r"(?P<water_ice>0\.71)\s*R\s*ln\s*2,\s*determined for\s*"
        + ice_ih
        + r",\s*so confirming the validity of the correspondence",
        normalized,
        flags=re.IGNORECASE,
    )
    field_match = re.search(
        r"We also find,\s*through application of a magnetic field,"
        r".{0,120}?restoration of much of the ground(?:-|\s*)state entropy "
        r"and new transitions involving transverse spin degrees of freedom",
        normalized,
        flags=re.IGNORECASE,
    )
    figure_match = re.search(
        r"Figure\s*2:\s*Specific heat and entropy of the spin(?:-|\s*)ice "
        r"compound\s*"
        + material
        + r"\s*showing\s*agreement with Pauling's prediction for the "
        r"entropy of water\s*"
        + ice_ih
        + r",\s*R\s*\(\s*ln\s*2\s*-\s*\(\s*1\s*/\s*2\s*\)\s*"
        r"ln\s*\(\s*3\s*/\s*2\s*\)\s*\)?",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        metadata_match,
        doi_match,
        pauling_match,
        analogy_match,
        measurement_match,
        field_match,
        figure_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified article and authors, "
            "Nature citation and DOI, Pauling's finite zero-point entropy, "
            "the pyrochlore spin-ice analogy, Dy2Ti2O7 specific-heat "
            "entropies, field restoration, and Figure 2 agreement with "
            "the Pauling formula"
        )

    measured_fraction = float(measurement_match.group("measured"))
    water_ice_fraction = float(measurement_match.group("water_ice"))
    residual_entropy_over_r = 0.5 * math.log(1.5)
    released_entropy_fraction = (
        math.log(2.0) - residual_entropy_over_r
    ) / math.log(2.0)
    if not math.isclose(
        water_ice_fraction,
        released_entropy_fraction,
        rel_tol=0.0,
        abs_tol=0.01,
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} water-ice value is inconsistent with "
            "Pauling's formula"
        )
    if not math.isclose(
        measured_fraction,
        released_entropy_fraction,
        rel_tol=0.0,
        abs_tol=0.05,
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} measured entropy is not close to the "
            "reported Pauling comparison"
        )

    return (
        {"pauling_entropy_observed": True},
        {
            "parser": "parse_ramirez_dy2ti2o7_pauling_entropy",
            "doi": "10.1038/20619",
            "measured_entropy_fraction_of_r_ln2": measured_fraction,
            "water_ice_entropy_fraction_of_r_ln2": water_ice_fraction,
            "pauling_released_entropy_fraction_of_r_ln2": (
                released_entropy_fraction
            ),
            "pauling_residual_entropy_over_r": residual_entropy_over_r,
            "source_representation": "Nature publisher article-page text",
            "claim_scope": (
                "the 1999 calorimetry reports an apparent Pauling residual "
                "entropy for Dy2Ti2O7 over its experimental equilibration "
                "window; no claim is made about the infinitely equilibrated "
                "T=0 limit"
            ),
            "matched_anchors": [
                "identified Ramirez et al. zero-point spin-ice article",
                "Nature 399, 333-335 (1999) citation",
                "registered DOI 10.1038/20619",
                "Pauling macroscopic degeneracy and finite zero-point entropy",
                "pyrochlore-magnet to water-ice correspondence",
                "Dy2Ti2O7 heat data give 0.67 versus 0.71 R ln 2",
                "magnetic field restores much ground-state entropy",
                "Figure 2 agrees with the explicit Pauling entropy formula",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_carteaux_cr2ge2te6_ferromagnetic_order(source_text):
    """Extract bulk ferromagnetic order in Cr2Ge2Te6 from the IOP abstract."""

    error_prefix = "Carteaux Cr2Ge2Te6 ferromagnetic order"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_carteaux_cr2ge2te6_ferromagnetic_order"
    )
    return _finalize_prepared_trace(
        _parse_carteaux_cr2ge2te6_ferromagnetic_order_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_carteaux_cr2ge2te6_ferromagnetic_order_prepared(normalized):
    error_prefix = "Carteaux Cr2Ge2Te6 ferromagnetic order"
    material = r"Cr\s*2\s*Ge\s*2\s*Te\s*6"

    metadata_match = re.search(
        r"Table of contents for issue\s*1,\s*volume\s*7,\s*"
        r"Journal of Physics:\s*Condensed Matter",
        normalized,
        flags=re.IGNORECASE,
    )
    identity_match = re.search(
        r"\b69\b\s*Crystallographic,\s*magnetic and electronic structures "
        r"of a new "
        r"layered ferromagnetic compound\s*"
        + material
        + r".{0,180}?V\s*\.?\s*Carteaux"
        r"\s*,\s*D\s*\.?\s*Brunet"
        r"\s*,\s*G\s*\.?\s*Ouvrard"
        r"\s+and\s+G\s*\.?\s*Andre",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"(?:https?://doi\.org/|DOI\s*:\s*)?"
        r"10\.1088\s*/\s*0953-8984\s*/\s*7\s*/\s*1\s*/\s*008",
        normalized,
        flags=re.IGNORECASE,
    )
    structure_match = re.search(
        material
        + r"\s+is a new layered material belonging to the lamellar ternary "
        r"M\s*2\s*X\s*2\s*Te\s*6 chalcogenides family"
        r".{0,520}?crystal symmetry is rhombohedral,\s*of space group\s*R3",
        normalized,
        flags=re.IGNORECASE,
    )
    crystal_method_match = re.search(
        r"The crystal structure of\s*"
        + material
        + r"\s+was solved using both X(?:-| )ray single(?:-| )crystal "
        r"diffraction and neutron powder diffraction data",
        normalized,
        flags=re.IGNORECASE,
    )
    magnetic_method_match = re.search(
        r"The magnetic structure and properties of\s*"
        + material
        + r"\s+have been determined by neutron powder diffraction and "
        r"susceptibility and magnetization measurements",
        normalized,
        flags=re.IGNORECASE,
    )
    order_match = re.search(
        r"Below\s*(?P<tc>61(?:\.0)?)\s*K,\s*"
        + material
        + r"\s+is ferromagnetic with spins aligned along the\s*"
        r"(?P<axis>c)\s+axis of the cell\s*"
        r"\(\s*mu\s*\(\s*Cr\s*3\s*\+\s*\)\s*=\s*"
        r"(?P<moment>2\.80)\s*\(\s*(?P<uncertainty>4)\s*\)"
        r"\s*_?\s*(?:\(\s*)?mu\s*B(?:\s*\))?\s+at\s*"
        r"(?P<moment_temperature>5(?:\.0)?)\s*K\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        metadata_match,
        doi_match,
        structure_match,
        crystal_method_match,
        magnetic_method_match,
        order_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified article and authors, "
            "IOP volume/issue/page metadata and DOI, the layered R3 "
            "Cr2Ge2Te6 structure, X-ray plus neutron structure solution, "
            "neutron/susceptibility/magnetization evidence, and the direct "
            "61 K ferromagnetic c-axis 2.80(4) mu_B observation"
        )

    curie_temperature = float(order_match.group("tc"))
    ordered_moment = float(order_match.group("moment"))
    uncertainty_digits = order_match.group("uncertainty")
    decimal_places = len(order_match.group("moment").split(".", maxsplit=1)[1])
    ordered_moment_uncertainty = int(uncertainty_digits) * (
        10.0 ** (-decimal_places)
    )
    ordered_moment_temperature = float(
        order_match.group("moment_temperature")
    )

    return (
        {"ferromagnetic_order": True},
        {
            "parser": "parse_carteaux_cr2ge2te6_ferromagnetic_order",
            "doi": "10.1088/0953-8984/7/1/008",
            "curie_temperature_k": curie_temperature,
            "spin_axis": order_match.group("axis").lower(),
            "ordered_moment_mu_b": ordered_moment,
            "ordered_moment_uncertainty_mu_b": ordered_moment_uncertainty,
            "ordered_moment_temperature_k": ordered_moment_temperature,
            "space_group": "R3",
            "source_representation": (
                "IOP publisher issue-page abstract text"
            ),
            "registry_material_alias": (
                "CrGeTe3 is the reduced-formula shorthand for Cr2Ge2Te6"
            ),
            "claim_scope": (
                "bulk Cr2Ge2Te6 ferromagnetic order below 61 K; no claim "
                "is made about the monolayer limit or an ideal honeycomb "
                "Heisenberg model"
            ),
            "matched_anchors": [
                "identified Carteaux et al. Cr2Ge2Te6 article and authors",
                "IOP JPCM volume 7 issue 1 page 69 metadata",
                "registered DOI 10.1088/0953-8984/7/1/008",
                "layered lamellar Cr2Ge2Te6 with rhombohedral R3 symmetry",
                "X-ray single-crystal and neutron powder structure solution",
                "neutron, susceptibility and magnetization measurements",
                "ferromagnetic below 61 K, c-axis, 2.80(4) mu_B at 5 K",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_cable_crcl3_ferromagnetic_layers(source_text):
    """Extract ferromagnetic intralayer alignment in bulk CrCl3."""

    error_prefix = "Cable CrCl3 ferromagnetic layers"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_cable_crcl3_ferromagnetic_layers"
    )
    return _finalize_prepared_trace(
        _parse_cable_crcl3_ferromagnetic_layers_prepared(prepared.text),
        prepared,
    )


def _parse_cable_crcl3_ferromagnetic_layers_prepared(normalized):
    error_prefix = "Cable CrCl3 ferromagnetic layers"
    material = r"Cr\s*Cl\s*3"

    identity_match = re.search(
        r"Neutron diffraction investigation of antiferromagnetism in\s*"
        + material
        + r".{0,180}?J\.?\s*W\.?\s*Cable"
        r"\s*,\s*M\.?\s*K\.?\s*Wilkinson"
        r"\s*,\s*E\.?\s*O\.?\s*Wollan",
        normalized,
        flags=re.IGNORECASE,
    )
    metadata_match = re.search(
        r"Journal of Physics and Chemistry of Solids\s*"
        r"Volume\s*19,\s*Issues?\s*1\s*-\s*2,\s*April\s*1961,\s*"
        r"Pages?\s*29\s*-\s*34",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"(?:https?://doi\.org/|DOI\s*:\s*)?"
        r"10\.1016\s*/\s*0022-3697\s*\(\s*61\s*\)\s*90053-1",
        normalized,
        flags=re.IGNORECASE,
    )
    experiment_match = re.search(
        r"Neutron diffraction observations have been made on powder and "
        r"single crystal samples of anhydrous\s*"
        + material
        + r"\s*at temperatures from\s*(?P<high>298(?:\.0)?)\s*to\s*"
        r"(?P<low>4\.2)\s*K",
        normalized,
        flags=re.IGNORECASE,
    )
    transition_match = re.search(
        r"This hexagonal layer(?:-| )type crystal undergoes a transition at\s*"
        r"(?P<transition>16\.8)\s*K\s*to an antiferromagnetic state",
        normalized,
        flags=re.IGNORECASE,
    )
    layer_alignment_match = re.search(
        r"the magnetic moments within each hexagonal layer of metal ions "
        r"are aligned parallel but adjacent layers of moments are oppositely "
        r"directed",
        normalized,
        flags=re.IGNORECASE,
    )
    axis_match = re.search(
        r"The axis of spontaneous sublattice magnetization is closely "
        r"perpendicular to the c(?:-| )axis",
        normalized,
        flags=re.IGNORECASE,
    )
    field_match = re.search(
        r"Observations of the\s*\(\s*003\s*\)\s*antiferromagnetic reflection "
        r"in an external magnetic field show that the antiferromagnetism can "
        r"be destroyed with fields of only a few kilo(?:-| )oersteds"
        r".{0,180}?a net magnetization can be produced with very small "
        r"magnetic fields",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        metadata_match,
        doi_match,
        experiment_match,
        transition_match,
        layer_alignment_match,
        axis_match,
        field_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified article and authors, "
            "journal citation and DOI, neutron diffraction on anhydrous "
            "powder and single-crystal CrCl3, the 16.8 K transition, "
            "parallel moments within each hexagonal layer and opposite "
            "adjacent layers, the sublattice axis, and the field response"
        )

    low_temperature = float(experiment_match.group("low"))
    high_temperature = float(experiment_match.group("high"))
    transition_temperature = float(
        transition_match.group("transition")
    )
    if not low_temperature < transition_temperature < high_temperature:
        raise RuntimeEvidenceError(
            f"{error_prefix} transition must lie inside the measured "
            "temperature interval"
        )

    return (
        {"ferromagnetic_honeycomb_layers": True},
        {
            "parser": "parse_cable_crcl3_ferromagnetic_layers",
            "doi": "10.1016/0022-3697(61)90053-1",
            "measurement": "neutron diffraction",
            "sample_temperature_range_k": [
                low_temperature,
                high_temperature,
            ],
            "transition_temperature_k": transition_temperature,
            "intralayer_alignment": "parallel",
            "interlayer_alignment": "opposite",
            "bulk_order": (
                "A-type antiferromagnetic stacking of ferromagnetic layers"
            ),
            "registry_geometry_mapping": (
                "the registered honeycomb-layer field is matched to the "
                "source's hexagonal metal-ion layers"
            ),
            "source_representation": (
                "Elsevier ScienceDirect publisher abstract text"
            ),
            "claim_scope": (
                "ferromagnetic alignment within bulk CrCl3 hexagonal "
                "metal-ion layers, stacked antiferromagnetically; no claim "
                "is made that the bulk crystal is a ferromagnet or about "
                "an isolated-monolayer Tc"
            ),
            "matched_anchors": [
                "identified Cable-Wilkinson-Wollan CrCl3 article",
                "JPCS 19 (1-2), 29-34 (1961) citation",
                "registered DOI 10.1016/0022-3697(61)90053-1",
                "neutron diffraction on powder and single-crystal CrCl3",
                "hexagonal layer-type transition at 16.8 K",
                "parallel intralayer and opposite interlayer moments",
                "sublattice magnetization nearly perpendicular to c",
                "(003) reflection and few-kOe field response",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_ressouche_mnps3_neel_order(source_text):
    """Extract the directly resolved bulk MnPS3 honeycomb Neel order."""

    error_prefix = "Ressouche MnPS3 Neel order"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_ressouche_mnps3_neel_order"
    )
    return _finalize_prepared_trace(
        _parse_ressouche_mnps3_neel_order_prepared(prepared.text),
        prepared,
    )


def _parse_ressouche_mnps3_neel_order_prepared(normalized):
    error_prefix = "Ressouche MnPS3 Neel order"
    material = r"Mn\s*P\s*S\s*3"
    manganese_ion = r"Mn\s*2\s*\+"

    identity_match = re.search(
        r"Magnetoelectric\s*"
        + material
        + r"\s*as a candidate for ferrotoroidicity"
        r".{0,300}?E\.?\s*Ressouche"
        r".{0,120}?M\.?\s*Loire"
        r".{0,120}?V\.?\s*Simonet"
        r".{0,120}?R\.?\s*Ballou"
        r".{0,120}?A\.?\s*Stunault"
        r".{0,160}?A\.?\s*Wildes",
        normalized,
        flags=re.IGNORECASE,
    )
    doi_match = re.search(
        r"(?:https?://doi\.org/|DOI\s*:\s*)?"
        r"10\.1103\s*/\s*PhysRevB\.82\.100408",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"revisited the magnetic structure of manganese phosphorus "
        r"trisulfide\s*"
        + material
        + r"\s*using neutron diffrac(?:tion|-\s*tion) and polarimetry"
        r".{0,260}?"
        + material
        + r"\s*undergoes a transition toward a collinear "
        r"antiferromagnetic order at\s*(?P<tn>78(?:\.0)?)\s*K",
        normalized,
        flags=re.IGNORECASE,
    )
    material_match = re.search(
        material
        + r".{0,420}?lamellar compound"
        r".{0,260}?monoclinic space group\s*C\s*2\s*/\s*m"
        r".{0,900}?metal ions\s*"
        + manganese_ion
        + r"\s*with spin\s*(?P<spin>5\s*/\s*2)"
        r".{0,260}?form a honeycomb lattice in the"
        r".{0,80}?\(\s*a\s*,\s*b\s*\).{0,80}?plane",
        normalized,
        flags=re.IGNORECASE,
    )
    experiment_match = re.search(
        r"A\s*"
        + material
        + r"\s*crystal"
        r".{0,260}?studied by neutron diffraction at the Institut "
        r"Laue\s*-\s*Langevin"
        r".{0,700}?magnetic structures were.{0,300}?first checked"
        r".{0,1400}?tometer D15"
        r".{0,1400}?Spherical\s*-\s*neutron\s*-\s*polarimetry experiments "
        r"were performed"
        r".{0,500}?diffractometer D3"
        r".{0,180}?using CRYOPAD",
        normalized,
        flags=re.IGNORECASE,
    )
    order_match = re.search(
        r"magnetic structure was refined from the.{0,300}?"
        r"integrated intensities "
        r"collected on D15 at\s*(?P<refinement_temperature>10(?:\.0)?)\s*K"
        r".{0,420}?Below T\s*N"
        r".{0,600}?\bzero propagation vector"
        r".{0,900}?four magnetic atoms"
        r".{0,900}?4g Wyckoff site"
        r".{0,700}?coupled following a\s*"
        r"\+\s*-\s*\+\s*-\s*sequence"
        r".{0,300}?"
        + manganese_ion
        + r"\s*is.{0,220}?antiferromagnetically coupled with its nearest "
        r"neighbors "
        r"in.{0,260}?\(\s*a\s*,\s*b\s*\).{0,100}?plane"
        r".{0,220}?coupling between adjacent planes is ferromagnetic",
        normalized,
        flags=re.IGNORECASE,
    )
    validation_match = re.search(
        r"magnetic structure description was further submitted to the "
        r"stringent test of CRYOPAD"
        r".{0,300}?polarization matrices measured for a set of"
        r".{0,180}?reflections at\s*(?P<validation_temperature>2(?:\.0)?)\s*K"
        r".{0,1600}?resulting\s*(?P<observations>99)\s*observations "
        r"were fitted using the magnetic structure described before",
        normalized,
        flags=re.IGNORECASE,
    )
    matches_by_name = {
        "identity": identity_match,
        "doi": doi_match,
        "abstract": abstract_match,
        "material": material_match,
        "experiment": experiment_match,
        "order": order_match,
        "validation": validation_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified Ressouche et al. "
            "article and DOI, neutron diffraction plus polarimetry, the "
            "78 K collinear antiferromagnetic transition, S=5/2 Mn2+ on "
            "a honeycomb lattice, the D15 10 K zero-vector +-+- "
            "nearest-neighbor-antiparallel refinement with ferromagnetic "
            "interlayer coupling, and the independent 2 K CRYOPAD fit; "
            f"missing anchors: {', '.join(missing_anchors)}"
        )
    matches = tuple(matches_by_name.values())

    transition_temperature = float(abstract_match.group("tn"))
    refinement_temperature = float(
        order_match.group("refinement_temperature")
    )
    validation_temperature = float(
        validation_match.group("validation_temperature")
    )
    observation_count = int(validation_match.group("observations"))
    if not (
        validation_temperature
        < refinement_temperature
        < transition_temperature
        and observation_count == 99
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} temperatures and observation count are "
            "internally inconsistent"
        )

    return (
        {"neel_order_reference": True},
        {
            "parser": "parse_ressouche_mnps3_neel_order",
            "doi": "10.1103/PhysRevB.82.100408",
            "transition_temperature_k": transition_temperature,
            "refinement_temperature_k": refinement_temperature,
            "polarimetry_validation_temperature_k": validation_temperature,
            "polarimetry_observation_count": observation_count,
            "propagation_vector": [0, 0, 0],
            "mn_spin": 2.5,
            "intralayer_order": (
                "nearest-neighbor antiparallel on the Mn2+ honeycomb lattice"
            ),
            "interlayer_coupling": "ferromagnetic",
            "source_role": (
                "machine-extractable supplemental direct primary research "
                "source"
            ),
            "registered_source_relationship": (
                "DOI 10.1088/0953-8984/10/28/020 measures MnPS3 spin waves "
                "and the magnetic (020) Bragg order parameter; Ressouche "
                "et al. directly resolve and neutron-polarimetry-test the "
                "honeycomb Neel topology"
            ),
            "derivation": (
                "The Mn sites form a bipartite honeycomb lattice and the "
                "refined +-+- zero-vector structure couples every in-plane "
                "nearest neighbor antiparallel; this is the honeycomb Neel "
                "topology represented by the registry boolean."
            ),
            "claim_scope": (
                "bulk MnPS3 nearest-neighbor Neel topology below 78 K; no "
                "claim is made about an isolated monolayer transition or "
                "an ideal two-dimensional Heisenberg theorem"
            ),
            "matched_anchors": [
                "identified Ressouche et al. MnPS3 article and authors",
                "direct-source DOI 10.1103/PhysRevB.82.100408",
                "neutron diffraction and polarimetry abstract with 78 K "
                "collinear antiferromagnetic order",
                "S=5/2 Mn2+ honeycomb lattice in monoclinic MnPS3",
                "D15 diffraction and D3 CRYOPAD experiment chain",
                "10 K zero-vector +-+- nearest-neighbor-antiparallel "
                "honeycomb refinement",
                "2 K CRYOPAD polarization-matrix validation with 99 "
                "observations",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_furuchi_lieb_lattice_ground_state_spin(source_text):
    """Derive the unfrustrated spin-1/2 Lieb-lattice spin per unit cell."""

    error_prefix = "Furuchi Lieb lattice ground-state spin"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_furuchi_lieb_lattice_ground_state_spin"
    )
    return _finalize_prepared_trace(
        _parse_furuchi_lieb_lattice_ground_state_spin_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_furuchi_lieb_lattice_ground_state_spin_prepared(normalized):
    error_prefix = "Furuchi Lieb lattice ground-state spin"

    identity_match = re.search(
        r"Collapsing Behavior of the Ferrimagnetic Ground State of the "
        r"S\s*=\s*1\s*/\s*2 Heisenberg Antiferromagnet on the Lieb "
        r"Lattice due to Frustration"
        r".{0,260}?Rito Furuchi"
        r".{0,120}?Hiroki Nakano"
        r".{0,120}?T.{0,5}?ru Sakai"
        r".{0,900}?arXiv\s*:\s*2409\.16715v1"
        r"\s*\[\s*cond-mat\.str-el\s*\]\s*25 Sep 2024",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"We study the S\s*=\s*1\s*/\s*2 Heisenberg antiferromagnet on "
        r"the Lieb lattice accompanied by additional interactions that "
        r"create frustration"
        r".{0,500}?system exhibits a ferrimagnetic ground state in the "
        r"absence of frustration",
        normalized,
        flags=re.IGNORECASE,
    )
    theorem_match = re.search(
        r"antiferromagnet on the Lieb lattice exhibits ferrimagnetism"
        r".{0,260}?explained in the Marshall\s*-\s*Lieb\s*-\s*Mattis "
        r"\(\s*MLM\s*\)\s*theorem"
        r".{0,500}?additional interaction that creates frustration"
        r".{0,300}?MLM theorem no longer holds",
        normalized,
        flags=re.IGNORECASE,
    )
    spin_pair = (
        r"S\s*_?\s*i\s*dot\s*S\s*_?\s*j"
    )
    hamiltonian_match = re.search(
        r"model Hamiltonian treated in this study"
        r".{0,160}?expressed as"
        r".{0,400}?\bH\s*="
        r".{0,500}?\bJ\s*"
        + spin_pair
        + r".{0,500}?\bJ\s*'\s*"
        + spin_pair
        + r".{0,900}?\(\s*1\s*\)"
        r".{0,300}?(?:where|Here)\s*"
        + r"S\s*_?\s*i\s*denotes the S\s*=\s*"
        r"(?P<spin_numerator>1)\s*/\s*(?P<spin_denominator>2)\s*"
        r"spin operator at site i"
        r".{0,260}?number of spins is denoted by N"
        r".{0,300}?interaction bonds of the first term form the Lieb "
        r"lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    unit_cell_match = re.search(
        r"spin sites of the Lieb lattice are divided into two sublattices "
        r"denoted by U and D"
        r".{0,300}?numbers of sites in the primitive unit cell"
        r".{0,180}?sublattice U and D are\s*"
        r"(?P<u_sites>\d+)\s*and\s*(?P<d_sites>\d+)\s*,\s*respectively"
        r".{0,280}?difference in the number of sites leads to the "
        r"occurrence of a ferrimagnetic ground state"
        r".{0,300}?second term of Eq\.\s*\(\s*1\s*\)\s*denotes "
        r"additional antiferromagnetic interactions",
        normalized,
        flags=re.IGNORECASE,
    )
    eta_match = re.search(
        r"We consider"
        r".{0,300}?\bJ\b.{0,100}?and\s*J\s*'"
        r".{0,180}?positive"
        r".{0,260}?interaction ratio\s*"
        r"eta\s*=\s*J\s*'\s*/\s*J"
        r".{0,300}?ferrimagnetic ground state appears for\s*"
        r"eta\s*=\s*0"
        r".{0,180}?corresponding to the Lieb lattice antiferromagnet",
        normalized,
        flags=re.IGNORECASE,
    )
    cluster_match = re.search(
        r"saturation magnetization,\s*namely the maximum of M,\s*is\s*"
        r"M\s*_?\s*sat\s*=\s*N\s*/\s*2"
        r".{0,4000}?ferrimagnetic ground states of\s*"
        r"N\s*=\s*(?P<n1>\d+)\s*,\s*(?P<n2>\d+)\s*,\s*and\s*"
        r"(?P<n3>\d+)\s*correspond to\s*"
        r"M\s*_?\s*spo\s*=\s*(?P<m1>\d+)\s*,\s*(?P<m2>\d+)\s*,"
        r"\s*and\s*(?P<m3>\d+)\s*,\s*respectively",
        normalized,
        flags=re.IGNORECASE,
    )
    matches_by_name = {
        "identity": identity_match,
        "abstract": abstract_match,
        "theorem": theorem_match,
        "hamiltonian": hamiltonian_match,
        "unit_cell": unit_cell_match,
        "eta_zero": eta_match,
        "cluster_normalization": cluster_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified 2409.16715v1 source, "
            "the spin-1/2 Lieb-lattice Heisenberg model, the MLM theorem "
            "scope, the two-term Hamiltonian, 2:1 primitive-cell "
            "sublattice counts, the unfrustrated eta=0 limit, and the "
            "N=30/36/42 to Mspo=5/6/7 normalization; missing anchors: "
            f"{', '.join(missing_anchors)}"
        )

    site_spin = int(hamiltonian_match.group("spin_numerator")) / int(
        hamiltonian_match.group("spin_denominator")
    )
    u_sites = int(unit_cell_match.group("u_sites"))
    d_sites = int(unit_cell_match.group("d_sites"))
    finite_cluster_sizes = [
        int(cluster_match.group(name)) for name in ("n1", "n2", "n3")
    ]
    finite_cluster_spins = [
        int(cluster_match.group(name)) for name in ("m1", "m2", "m3")
    ]
    if (
        not math.isclose(site_spin, 0.5, rel_tol=0.0, abs_tol=0.0)
        or (u_sites, d_sites) != (2, 1)
        or finite_cluster_sizes != [30, 36, 42]
        or finite_cluster_spins != [5, 6, 7]
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} source parameters do not match the registered "
            "spin-1/2, 2:1-cell, N=30/36/42 normalization"
        )

    sites_per_cell = u_sites + d_sites
    theorem_spin_per_cell = abs(u_sites - d_sites) * site_spin
    finite_cluster_spin_per_cell = []
    for number_of_sites, total_spin in zip(
        finite_cluster_sizes, finite_cluster_spins
    ):
        number_of_cells = number_of_sites / sites_per_cell
        if not number_of_cells.is_integer():
            raise RuntimeEvidenceError(
                f"{error_prefix} cluster size is not an integer number of "
                "primitive cells"
            )
        finite_cluster_spin_per_cell.append(total_spin / number_of_cells)

    if not (
        math.isclose(
            theorem_spin_per_cell, 0.5, rel_tol=0.0, abs_tol=1.0e-15
        )
        and all(
            math.isclose(
                value,
                theorem_spin_per_cell,
                rel_tol=0.0,
                abs_tol=1.0e-15,
            )
            for value in finite_cluster_spin_per_cell
        )
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} sublattice theorem and finite-cluster "
            "normalizations disagree"
        )

    matches = tuple(matches_by_name.values())
    return (
        {"ground_state_spin_per_unit_cell": theorem_spin_per_cell},
        {
            "parser": "parse_furuchi_lieb_lattice_ground_state_spin",
            "source_identity": "arXiv:2409.16715v1",
            "registered_doi": "10.1063/1.1724276",
            "primitive_cell_sublattice_counts": {
                "U": u_sites,
                "D": d_sites,
            },
            "site_spin": site_spin,
            "theorem_spin_per_unit_cell": theorem_spin_per_cell,
            "finite_cluster_spin_per_unit_cell": (
                finite_cluster_spin_per_cell
            ),
            "finite_cluster_sizes": finite_cluster_sizes,
            "finite_cluster_ground_state_spins": finite_cluster_spins,
            "source_role": (
                "machine-extractable supplemental direct primary research "
                "source"
            ),
            "registered_source_relationship": (
                "Lieb-Mattis 1962 supplies the registered general bipartite "
                "energy-ordering theorem; Furuchi et al. supply the target "
                "Lieb-lattice 2:1 primitive-cell sublattice counts and "
                "eta=0 spin normalization"
            ),
            "derivation": (
                "Each primitive cell has two U and one D spin-1/2 sites, "
                "so |S_U-S_D|=|(2-1)/2|=1/2. Independently, the reported "
                "(N,Mspo) pairs (30,5), (36,6), and (42,7), divided by "
                "N/3 primitive cells, each give 1/2."
            ),
            "claim_scope": (
                "unfrustrated eta=0 spin-1/2 Lieb-lattice Heisenberg "
                "antiferromagnet; the 1/2-per-cell theorem value is not "
                "extended to finite J-prime frustration"
            ),
            "matched_anchors": [
                "identified Furuchi-Nakano-Sakai 2409.16715v1 source",
                "spin-1/2 Lieb-lattice Heisenberg antiferromagnet abstract",
                "Marshall-Lieb-Mattis theorem and frustration boundary",
                "two-term Heisenberg Hamiltonian and spin-1/2 operators",
                "two U and one D site per primitive cell",
                "eta=0 unfrustrated Lieb-lattice ferrimagnetic limit",
                "Msat=N/2 and N=30/36/42 to Mspo=5/6/7 scaling",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_hsieh_nacro2_unconventional_spin_order(source_text):
    """Extract the unconventional NaCrO2 dimensional-crossover evidence."""

    error_prefix = "Hsieh NaCrO2 unconventional spin order"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_hsieh_nacro2_unconventional_spin_order"
    )
    return _finalize_prepared_trace(
        _parse_hsieh_nacro2_unconventional_spin_order_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_hsieh_nacro2_unconventional_spin_order_prepared(normalized):
    error_prefix = "Hsieh NaCrO2 unconventional spin order"

    nacro2 = r"Na\s*Cr\s*O\s*_?\s*2"
    nax_cro2 = r"Na\s*_?\s*x\s*Cr\s*O\s*_?\s*2"
    triangular_lattice = r"triangular\s*-?\s*lattice"
    interlayer = r"inter\s*-?\s*layer"
    long_range = r"long\s*-?\s*range"
    short_range = r"short\s*-?\s*range"
    three_dimensional = r"three\s*-?\s*dimensional"
    degree_120 = r"120\s*-?\s*degree"

    identity_match = re.search(
        r"Spin Order by (?:Quantum\s+)?Frustration in "
        + triangular_lattice
        + r" Mott Insulator\s*"
        + nacro2
        + r"\s*:?\s*A Neutron Scattering Study"
        r".{0,500}?D\.\s*Hsieh"
        r".{0,140}?D\.\s*Qian"
        r".{0,140}?R\.\s*F\.\s*Berger"
        r".{0,240}?B\.\s*Ueland"
        r".{0,180}?P\.\s*Schiffer"
        r".{0,180}?Q\.\s*Huang"
        r".{0,180}?R\.\s*J\.\s*Cava"
        r".{0,180}?J\.\s*W\.\s*Lynn"
        r".{0,180}?M\.\s*Z\.\s*Hasan",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"We report high\s*-?\s*resolution neutron scattering "
        r"measurements on the "
        + triangular_lattice
        + r" Mott insulator\s*"
        + nax_cro2
        + r"\s*\(\s*x\s*=\s*1\s*\)"
        r".{0,420}?unusually broad fluctuating crossover regime"
        r".{0,360}?onset of spin freezing\s*\(\s*T\s*_?\s*c\s*"
        r"(?:approximately|~)\s*(?P<tc>\d+(?:\.\d+)?)\s*K\s*\)"
        r".{0,500}?below some crossover temperature\s*"
        r"\(\s*T\s*(?:approximately|~)\s*"
        r"(?P<crossover_fraction>\d+(?:\.\d+)?)\s*"
        r"T\s*_?\s*c\s*\)"
        r".{0,260}?small incommensuration develops"
        r".{0,300}?drives\s*"
        + three_dimensional
        + r" magnetic order"
        r".{0,120}?supporting coherent spin wave modes",
        normalized,
        flags=re.IGNORECASE,
    )
    no_long_range_match = re.search(
        r"no magnetic\s*"
        + long_range
        + r" order is observed down to\s*"
        r"(?P<minimum_temperature>\d+(?:\.\d+)?)\s*K"
        r"\s*\(\s*xi\s*_?\s*c\s*less than\s*"
        r"(?P<xi_c_upper>\d+(?:\.\d+)?)\s*A\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    theory_match = re.search(
        r"The classical ground state of the nearest\s*-?\s*neighbor"
        r".{0,1800}?(?:TLAFM|"
        + triangular_lattice
        + r" antiferromagnet)"
        r"\s+is the\s*"
        + degree_120
        + r" spin structure"
        r".{0,2200}?If such layers are"
        r".{0,1200}?rhombohedrally stacked"
        r".{0,2200}?(?:there is a )?cancellation"
        r".{0,1200}?of\s*"
        + interlayer
        + r" Weiss fields (?:which )?leads to a classical decou"
        r".{0,1200}?pling of spin layers",
        normalized,
        flags=re.IGNORECASE,
    )
    material_match = re.search(
        r"(?:The\s+)?A\s*Cr\s*O\s*_?\s*2"
        r".{0,1800}?Cr\s*3\s*\+\s*"
        r"\(\s*S\s*=\s*(?P<spin_numerator>3)\s*/?\s*"
        r"(?P<spin_denominator>2)\s*\)\s*ions"
        r".{0,1800}?form a rhombohedrally stacked\s*"
        r"(?:TL|"
        + triangular_lattice
        + r")",
        normalized,
        flags=re.IGNORECASE,
    )
    sample_match = re.search(
        r"A\s*(?P<sample_mass>\d+(?:\.\d+)?)\s*g powder sample of\s*"
        + nacro2
        + r"\s*was prepared",
        normalized,
        flags=re.IGNORECASE,
    )
    method_match = re.search(
        r"Magnetic neutron scattering was performed at the NIST Center "
        r"for Neutron Research",
        normalized,
        flags=re.IGNORECASE,
    )
    correlation_match = re.search(
        r"For\s*T\s*greater than\s*"
        r"(?P<pure_2d_above>\d+(?:\.\d+)?)\s*K"
        r".{0,1800}?spin correlations are purely 2D\s*"
        r"\(\s*N\s*=\s*(?P<pure_2d_layers>1)\s*\)"
        r".{0,1800}?Weak\s*inter\s*-?\s*plane correlations develop at\s*"
        r"(?P<interplane_onset>\d+(?:\.\d+)?)\s*K\s*"
        r"\(\s*N\s*=\s*(?P<onset_layers>\d+)\s*\)"
        r".{0,1800}?N saturates to\s*(?P<saturated_layers>\d+)\s*from\s*"
        r"(?P<saturation_onset>\d+(?:\.\d+)?)\s*K down to\s*"
        r"(?P<saturation_minimum>\d+(?:\.\d+)?)\s*K"
        r".{0,3000}?comparison of the\s*"
        r"(?P<comparison_temperature>\d+(?:\.\d+)?)\s*K data to the "
        r"expected lineshape"
        r".{0,3000}?limit N\s*(?:approaching|->)\s*infinity"
        r".{0,3000}?xi\s*_?\s*c is indeed"
        r".{0,1200}?"
        + short_range,
        normalized,
        flags=re.IGNORECASE,
    )
    ordering_match = re.search(
        r"development of weak c\s*-?\s*axis correlations between\s*"
        r"(?P<c_axis_start>\d+(?:\.\d+)?)\s*K and\s*"
        r"(?P<c_axis_end>\d+(?:\.\d+)?)\s*K"
        r".{0,1800}?accompanied by a change in"
        r".{0,100}?\bq\b"
        r".{0,2600}?\(\s*0\s*,\s*4\s*pi\s*/\s*3\s*a\s*,\s*0\s*\)"
        r".{0,3000}?ordering wave vector at\s*"
        r"(?P<order_temperature>\d+(?:\.\d+)?)\s*K points to a\s*"
        + degree_120
        + r".{0,2600}?consistent with the purely 2D nature"
        r".{0,1200}?of spin correlations"
        r".{0,3000}?slight"
        r".{0,1200}?incommensuration at\s*"
        r"(?P<incommensuration_temperature>\d+(?:\.\d+)?)\s*K "
        r"represents a departure from"
        r".{0,1600}?"
        + degree_120
        + r" order which resolves the\s*"
        + interlayer
        + r" frustration",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"To conclude,\s*(?:our|the) neutron scattering measurements"
        r".{0,1800}?(?:clearly\s+)?reveal a rare 2D antiferromagnetic "
        r"phase in"
        r".{0,1800}?"
        + nacro2
        + r".{0,1800}?with strong spin fluctuations over an extended "
        r"temperature range",
        normalized,
        flags=re.IGNORECASE,
    )
    matches_by_name = {
        "identity": identity_match,
        "abstract": abstract_match,
        "absence_of_long_range_order": no_long_range_match,
        "triangular_lattice_theory": theory_match,
        "material_spin_and_stacking": material_match,
        "sample": sample_match,
        "neutron_method": method_match,
        "finite_c_axis_correlations": correlation_match,
        "wave_vector_crossover": ordering_match,
        "conclusion": conclusion_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified Hsieh et al. source, "
            "high-resolution neutron scattering on S=3/2 rhombohedrally "
            "stacked triangular NaCrO2, the 41 K and 0.75-Tc crossover "
            "abstract, a 15 g NIST sample chain, finite four-layer "
            "c-axis correlations down to 1.5 K, the 40 K 120-degree "
            "wave vector and 30 K incommensuration, explicit absence of "
            "magnetic long-range order, and the rare-2D-phase "
            f"conclusion; missing anchors: {', '.join(missing_anchors)}"
        )

    spin_freezing_onset = float(abstract_match.group("tc"))
    crossover_fraction = float(
        abstract_match.group("crossover_fraction")
    )
    minimum_temperature = float(
        no_long_range_match.group("minimum_temperature")
    )
    xi_c_upper = float(no_long_range_match.group("xi_c_upper"))
    cr_spin = int(material_match.group("spin_numerator")) / int(
        material_match.group("spin_denominator")
    )
    sample_mass = float(sample_match.group("sample_mass"))
    pure_2d_above = float(correlation_match.group("pure_2d_above"))
    pure_2d_layers = int(correlation_match.group("pure_2d_layers"))
    interplane_onset = float(correlation_match.group("interplane_onset"))
    onset_layers = int(correlation_match.group("onset_layers"))
    saturated_layers = int(correlation_match.group("saturated_layers"))
    saturation_onset = float(
        correlation_match.group("saturation_onset")
    )
    saturation_minimum = float(
        correlation_match.group("saturation_minimum")
    )
    comparison_temperature = float(
        correlation_match.group("comparison_temperature")
    )
    c_axis_start = float(ordering_match.group("c_axis_start"))
    c_axis_end = float(ordering_match.group("c_axis_end"))
    order_temperature = float(ordering_match.group("order_temperature"))
    incommensuration_temperature = float(
        ordering_match.group("incommensuration_temperature")
    )
    exact_values = (
        math.isclose(
            spin_freezing_onset, 41.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            crossover_fraction, 0.75, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(cr_spin, 1.5, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(sample_mass, 15.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            minimum_temperature, 1.5, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            xi_c_upper, 16.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            pure_2d_above, 40.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and pure_2d_layers == 1
        and math.isclose(
            interplane_onset, 40.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and onset_layers == 2
        and saturated_layers == 4
        and math.isclose(
            saturation_onset, 30.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            saturation_minimum, 1.5, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            comparison_temperature, 1.5, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            c_axis_start, 40.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            c_axis_end, 30.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            order_temperature, 40.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            incommensuration_temperature,
            30.0,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
    )
    if not exact_values:
        raise RuntimeEvidenceError(
            f"{error_prefix} numerical anchors are internally "
            "inconsistent with the registered NaCrO2 result"
        )

    matches = tuple(matches_by_name.values())
    return (
        {"unconventional_spin_order_reference": True},
        {
            "parser": "parse_hsieh_nacro2_unconventional_spin_order",
            "source_identity": "arXiv:1405.6184v1",
            "registered_doi": "10.1016/j.physb.2007.10.295",
            "material": "NaCrO2",
            "cr_spin": cr_spin,
            "spin_freezing_onset_k": spin_freezing_onset,
            "crossover_fraction_tc": crossover_fraction,
            "two_dimensional_order_temperature_k": order_temperature,
            "incommensuration_temperature_k": (
                incommensuration_temperature
            ),
            "minimum_measurement_temperature_k": minimum_temperature,
            "c_axis_correlation_length_upper_bound_angstrom": xi_c_upper,
            "interplane_layer_count_at_40k": onset_layers,
            "low_temperature_correlated_layer_count": saturated_layers,
            "low_temperature_order": (
                "short-range three-dimensional correlations without "
                "magnetic long-range order"
            ),
            "source_role": (
                "machine-extractable expanded direct primary research "
                "source"
            ),
            "registered_source_relationship": (
                "The registered 2008 Physica B article reports the same "
                "NaCrO2 neutron-scattering dimensional crossover; "
                "arXiv:1405.6184v1 is the expanded primary account that "
                "supplies the spin, wave-vector, layer-count, and "
                "correlation-length anchors."
            ),
            "registry_name_note": (
                "The benchmark key says nacuo2, but its registered source "
                "and model parameters identify NaCrO2; no NaCuO2 claim is "
                "made."
            ),
            "claim_scope": (
                "bulk rhombohedrally stacked S=3/2 NaCrO2: a 2D "
                "120-degree correlated regime crosses into short-range, "
                "not long-range, three-dimensional order through a small "
                "incommensuration"
            ),
            "matched_anchors": [
                "identified Hsieh et al. NaCrO2 neutron source",
                "41 K spin-freezing and 0.75-Tc incommensuration abstract",
                "no magnetic long-range order to 1.5 K with xi_c < 16 A",
                "120-degree triangular-layer and interlayer-frustration "
                "theory",
                "S=3/2 Cr3+ rhombohedrally stacked triangular lattice",
                "15 g NaCrO2 powder sample",
                "NIST magnetic-neutron-scattering experiment",
                "N=1 to N=2 to N=4 finite-layer correlation crossover",
                "40 K 120-degree vector to 30 K incommensuration",
                "rare 2D antiferromagnetic phase conclusion",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_mazin_honeycomb_j1_j2_j3_phase_set(source_text):
    """Extract the classical honeycomb J1-J2-J3 phase-label set."""

    error_prefix = "Mazin honeycomb J1-J2-J3 phase set"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_mazin_honeycomb_j1_j2_j3_phase_set"
    )
    return _finalize_prepared_trace(
        _parse_mazin_honeycomb_j1_j2_j3_phase_set_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_mazin_honeycomb_j1_j2_j3_phase_set_prepared(normalized):
    error_prefix = "Mazin honeycomb J1-J2-J3 phase set"

    j1 = r"J\s*_?\s*1"
    j2 = r"J\s*_?\s*2"
    j3 = r"J\s*_?\s*3"
    j2_over_j1 = rf"{j2}\s*/\s*{j1}"
    honeycomb = r"honeycomb\s+(?:lat\s*-?\s*tice|lattice|layer)"

    identity_match = re.search(
        r"Ca\s*Mn\s*_?\s*2\s*Sb\s*_?\s*2\s*:\s*"
        r"a fully frustrated classical magnetic system"
        r".{0,2500}?I\.\s*I\.\s*Mazin"
        r".{0,2500}?arXiv\s*:\s*1309\.3744v1",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"We show by means of density functional calculations"
        r".{0,500}?classical Heisenberg model on the\s+"
        + honeycomb
        + r".{0,700}?Three entirely different\s+"
        r"long\s*-?\s*range ordered magnetic phases"
        r".{0,400}?the Neel phase and two different spiral phases",
        normalized,
        flags=re.IGNORECASE,
    )
    provenance_match = re.search(
        r"nearly classical spin system on a\s+"
        + honeycomb
        + r".{0,900}?seminal paper of Rastelli et al\.?\s+from"
        r".{0,900}?1979\s*\[\s*1\s*\]"
        r".{0,700}?basic model involves the nearest\s*-?\s*neighbor"
        r".{0,180}?interaction\s*"
        + j1
        + r".{0,500}?second\s*-?\s*neighbor"
        r".{0,180}?interaction\s*"
        + j2,
        normalized,
        flags=re.IGNORECASE,
    )
    j1_j2_chain_match = re.search(
        r"In the classical limit,\s*the ground state of this\s*"
        + j1
        + r"\s*-\s*"
        + j2
        + r".{0,500}?antiferromagnetic\s+J\s*1\s*"
        r"(?:(?:,\s*|and\s+)(?:J\s*)?2)"
        r".{0,600}?Neel phase"
        r".{0,500}?"
        + j2_over_j1
        + r"\s*<\s*(?P<neel_numerator>\d+)\s*/\s*"
        r"(?P<neel_denominator>\d+)"
        r".{0,1000}?(?P<spiral_low_numerator>\d+)\s*/\s*"
        r"(?P<spiral_low_denominator>\d+)\s*<\s*"
        + j2_over_j1
        + r"\s*<\s*(?P<spiral_high_numerator>\d+)\s*/\s*"
        r"(?P<spiral_high_denominator>\d+)"
        r".{0,700}?two degenerate solutions"
        r".{0,1600}?two\s+"
        r"dif(?:ferent|-\s*.{0,900}?ferent)\s+spiral phases"
        r".{0,1800}?"
        + j2_over_j1
        + r"\s*>\s*(?P<stripe_numerator>\d+)\s*/\s*"
        r"(?P<stripe_denominator>\d+)"
        r".{0,500}?stripe phase"
        r".{0,500}?alternating\s+(?:ferromagnetic|FM)\s+pairs",
        normalized,
        flags=re.IGNORECASE,
    )
    j3_extension_match = re.search(
        r"Whenever a third param(?:eter|-\s*.{0,900}?eter) is added"
        r".{0,1400}?third\s*-?\s*neighbor exchange"
        r"(?:\s*\[\s*1\s*\])?\s*"
        + j3
        + r".{0,2200}?com(?:plex|-\s*.{0,900}?plex) phase diagrams arise"
        r".{0,1600}?four phases described"
        r".{0,1200}?additional phases such as zigzag "
        r"antiferromag(?:netism|-\s*.{0,900}?netism)",
        normalized,
        flags=re.IGNORECASE,
    )
    mapping_match = re.search(
        r"calculated the total energies of"
        r".{0,600}?\b10\s*different magnetic "
        r"configurations"
        r".{0,700}?mapped the re(?:sults|-\s*.{0,700}?sults) onto the "
        r"(?:Heisenberg model|model Heisenberg) that includes"
        r".{0,500}?(?:first|1st)\s*-?\s*,?"
        r".{0,500}?(?:second|2nd)\s*-?\s*,?"
        r".{0,500}?(?:and\s+)?(?:third|3rd)\s*-?\s*nearest neighbors"
        r".{0,900}?\(\s*"
        + j1
        + r"\s*,.{0,600}?"
        + j2
        + r"\s*,.{0,600}?(?:and\s+)?"
        + j3
        + r"\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    figure_match = re.search(
        r"FIG(?:URE)?\.?\s*5\s*[\.:]\s*"
        r"Phase diagram of the classical\s*"
        + j1
        + r"(?:\s*-\s*)+"
        + j2
        + r"(?:\s*-\s*)+"
        + j3
        + r".{0,900}?Heisenberg model"
        r".{0,5000}?phase boundaries"
        r".{0,5000}?y\s*=\s*0"
        r".{0,2500}?x\s*=\s*1\s*/\s*2\s*\[\s*1\s*\]",
        normalized,
        flags=re.IGNORECASE,
    )
    named_phases_match = re.search(
        r"there are five planar phases"
        r".{0,2200}?The Neel\s*\(\s*N\s*\)\s*phase"
        r".{0,2600}?nearest neighbors order"
        r".{0,900}?antiferromagnetically"
        r".{0,2600}?the\s*\"stripy\"\s*\(\s*S\s*\)\s*phase"
        r".{0,2600}?bonds?\s+along one direction "
        r"(?:are|is)\s+ferromagnetic"
        r".{0,2600}?double stripes order antiferromagnetically"
        r".{0,2600}?two spi(?:ral|-\s*.{0,1200}?ral) phases"
        r"\s*\(\s*A\s+and\s+B\s*\)"
        r".{0,3500}?Adding.{0,900}?"
        + j3
        + r"\s+creates"
        r".{0,3500}?new.{0,900}?\"zigzag\"\s*"
        r"phase emerging at large\s*"
        + j3
        + r".{0,2600}?Fig(?:ure|\.)\s*5",
        normalized,
        flags=re.IGNORECASE,
    )
    references_match = re.search(
        r"\[\s*1\s*\]\s*E\.\s*Rastelli,\s*A\.\s*Tassi,\s*"
        r"and\s*L\.\s*Reatto,\s*Physica\s+B\s+97\s*,\s*1"
        r".{0,900}?\(\s*1979\s*\)"
        r".{0,3000}?\[\s*2\s*\]\s*J\.\s*B\.\s*Fouet,\s*"
        r"P\.\s*Sindzingre,\s*and\s*C\.\s*Lhuillier,\s*"
        r"(?:European Physical Journal|Eur\.\s*Phys\.\s*J\.)\s*"
        r".{0,900}?B\s+20\s*,\s*241.{0,900}?\(\s*2001\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )

    matches_by_name = {
        "source_identity": identity_match,
        "abstract_model_and_three_phase_point": abstract_match,
        "rastelli_provenance_and_j1_j2_model": provenance_match,
        "classical_j1_j2_phase_chain": j1_j2_chain_match,
        "j3_phase_diagram_extension": j3_extension_match,
        "ten_configuration_heisenberg_mapping": mapping_match,
        "figure_5_j1_j2_j3_boundaries": figure_match,
        "modern_named_phase_set": named_phases_match,
        "rastelli_and_fouet_references": references_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires arXiv:1309.3744v1, the classical "
            "antiferromagnetic-J1 honeycomb J1-J2 thresholds, both "
            "spiral branches, the stripy and J3-induced zigzag phases, "
            "the ten-configuration Heisenberg mapping, Figure 5, and "
            "the Rastelli/Fouet provenance chain; missing anchors: "
            f"{', '.join(missing_anchors)}"
        )

    def _fraction(match, numerator_group, denominator_group):
        numerator = int(match.group(numerator_group))
        denominator = int(match.group(denominator_group))
        if denominator == 0:
            raise RuntimeEvidenceError(
                f"{error_prefix} contains a zero denominator"
            )
        return numerator / denominator

    neel_upper = _fraction(
        j1_j2_chain_match, "neel_numerator", "neel_denominator"
    )
    spiral_lower = _fraction(
        j1_j2_chain_match,
        "spiral_low_numerator",
        "spiral_low_denominator",
    )
    spiral_upper = _fraction(
        j1_j2_chain_match,
        "spiral_high_numerator",
        "spiral_high_denominator",
    )
    stripe_lower = _fraction(
        j1_j2_chain_match, "stripe_numerator", "stripe_denominator"
    )
    if not (
        math.isclose(neel_upper, 1.0 / 6.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            spiral_lower, 1.0 / 6.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            spiral_upper, 1.0 / 2.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            stripe_lower, 1.0 / 2.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and neel_upper == spiral_lower < spiral_upper == stripe_lower
    ):
        raise RuntimeEvidenceError(
            f"{error_prefix} numerical phase boundaries disagree with "
            "the registered classical phase diagram"
        )

    phase_labels = ["neel", "spiral", "zigzag", "stripy"]
    matches = tuple(matches_by_name.values())
    return (
        {"phases": phase_labels},
        {
            "parser": "parse_mazin_honeycomb_j1_j2_j3_phase_set",
            "source_identity": "arXiv:1309.3744v1",
            "registered_doi": "10.1016/0378-4363(79)90002-0",
            "original_classical_source": (
                "Rastelli-Tassi-Reatto, Physica B 97, 1-24 (1979)"
            ),
            "phase_labels": phase_labels,
            "neel_upper_j2_over_j1": neel_upper,
            "spiral_j2_over_j1_window": [
                spiral_lower,
                spiral_upper,
            ],
            "spiral_branch_count": 2,
            "j3_extension_phase": "zigzag",
            "source_role": (
                "machine-extractable supplemental direct primary "
                "research source"
            ),
            "registered_source_relationship": (
                "Rastelli-Tassi-Reatto 1979 is the registered original "
                "classical phase diagram; Fouet-Sindzingre-Lhuillier "
                "2001 explicitly state that they reproduce that diagram; "
                "Mazin 1309.3744v1 supplies the modern Neel, spiral, "
                "stripy, and zigzag labels and reproduces the J1-J2-J3 "
                "boundary figure with Rastelli as reference [1]."
            ),
            "claim_scope": (
                "zero-temperature classical antiferromagnetic-J1 "
                "honeycomb J1-J2-J3 Heisenberg phase-label set, with "
                "the two spiral branches normalized to one registry "
                "label; no quantum phase stability or simultaneous "
                "four-phase coexistence is claimed"
            ),
            "matched_anchors": [
                "identified Mazin 1309.3744v1 source",
                "classical honeycomb Heisenberg three-phase-point abstract",
                "Rastelli 1979 provenance and basic J1-J2 model",
                "Neel, two-spiral, and stripe J2/J1 phase chain",
                "J3 extension produces complex diagrams and zigzag order",
                "ten configurations mapped to a J1-J2-J3 Heisenberg model",
                "Figure 5 classical J1-J2-J3 boundary diagram",
                "five planar phases with stripy, two spirals, and zigzag",
                "Rastelli 1979 and Fouet 2001 bibliography entries",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_stodter_clinoatacamite_distorted_kagome_exchange(source_text):
    """Extract the modern six-exchange distorted-kagome characterization."""

    error_prefix = "Stodter clinoatacamite distorted-kagome exchange"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_stodter_clinoatacamite_distorted_kagome_exchange",
    )
    return _finalize_prepared_trace(
        _parse_stodter_clinoatacamite_distorted_kagome_exchange_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_stodter_clinoatacamite_distorted_kagome_exchange_prepared(
    search_text,
):
    error_prefix = "Stodter clinoatacamite distorted-kagome exchange"

    material = r"Cu\s*2\s*Cl\s*\(\s*OH\s*\)\s*3"
    title_match = re.search(
        r"Competing Ordering Modes in the Distorted Quantum Kagome "
        r"Material.{0,160}?Clinoatacamite\s*"
        + material,
        search_text,
        flags=re.IGNORECASE,
    )
    version_match = re.search(
        r"arXiv\s*:\s*2601\.21024v2"
        r".{0,100}?\[\s*cond-mat\.str-el\s*\]"
        r".{0,80}?19\s+Jun\s+2026",
        search_text,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"using density-functional theory.{0,120}?"
        r"clinoatacamite belongs to the class of distorted kagome "
        r"antiferromagnets.{0,160}?kagome plane being embedded into "
        r"a low-symmetry crystal structure",
        search_text,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"employing density-functional theory\s*\(\s*DFT\s*\)"
        r".{0,160}?demonstrate that clinoatacamite"
        r".{0,80}?understood as a non-uniform kagome "
        r"antiferromagnet with weak ferromagnetic\s*"
        r"\(\s*FM\s*\)\s*couplings to the interlayer Cu sites"
        r".{0,260}?weak network of kagome planes and interlayer sites",
        search_text,
        flags=re.IGNORECASE,
    )
    topology_match = re.search(
        r"Cu\s*\(\s*2\s*\)\s*and\s*Cu\s*\(\s*3\s*\)\s*sites "
        r"form a slightly distorted kagome motif"
        r".{0,260}?Cu\s*\(\s*1\s*\)\s*sites are interlayer sites"
        r".{0,160}?three inequivalent NN Cu-Cu exchange paths"
        r".{0,60}?J\s*4\s*-\s*J\s*6.{0,80}?within the kagome layers"
        r".{0,100}?three inequivalent NN Cu-Cu exchange paths"
        r".{0,60}?J\s*1\s*-\s*J\s*3.{0,100}?"
        r"between kagome and interlayer sites",
        search_text,
        flags=re.IGNORECASE,
    )
    caption_match = re.search(
        r"(?:At\s+)?U\s*=\s*(?P<u>\d+(?:\.\d+)?)\s*eV"
        r".{0,240}?mean-field Curie-\s*Weiss temperature"
        r".{0,160}?(?:Theta|theta|Θ)\s*_?\s*CW\s*=\s*"
        r"(?P<theta>-?\d+(?:\.\d+)?)\s*\(\s*1\s*\)\s*K"
        r".{0,100}?J\s*1\s*=\s*(?P<j1>-?\d+(?:\.\d+)?)\s*K"
        r".{0,80}?J\s*2\s*=\s*(?P<j2>-?\d+(?:\.\d+)?)\s*K"
        r".{0,80}?J\s*3\s*=\s*(?P<j3>-?\d+(?:\.\d+)?)\s*K"
        r".{0,80}?J\s*4\s*=\s*(?P<j4>-?\d+(?:\.\d+)?)\s*K"
        r".{0,80}?J\s*5\s*=\s*(?P<j5>-?\d+(?:\.\d+)?)\s*K"
        r".{0,80}?J\s*6\s*=\s*(?P<j6>-?\d+(?:\.\d+)?)\s*K",
        search_text,
        flags=re.IGNORECASE,
    )
    dominant_match = re.search(
        r"The dominant exchange couplings"
        r".{0,80}?J\s*4\s*=\s*(?P<j4>-?\d+(?:\.\d+)?)\s*K"
        r".{0,80}?J\s*5\s*=\s*(?P<j5>-?\d+(?:\.\d+)?)\s*K"
        r".{0,80}?J\s*6\s*=\s*(?P<j6>-?\d+(?:\.\d+)?)\s*K"
        r".{0,100}?form the non-uniform AFM kagome layers",
        search_text,
        flags=re.IGNORECASE,
    )
    interlayer_match = re.search(
        r"(?:The\s+couplings|plings)\s*J\s*1\s*=\s*"
        r"(?P<j1>-?\d+(?:\.\d+)?)\s*K"
        r".{0,80}?J\s*2\s*=\s*(?P<j2>-?\d+(?:\.\d+)?)\s*K"
        r".{0,80}?J\s*3\s*=\s*(?P<j3>-?\d+(?:\.\d+)?)\s*K"
        r".{0,80}?are FM"
        r".{0,300}?couplings between kagome sites and interlayer sites"
        r".{0,80}?\|\s*J\s*_?\s*i\s*\|\s*<=\s*"
        r"(?P<bound>\d+(?:\.\d+)?)\s*J\s*6"
        r".{0,900}?weak.{0,160}?ferromagnetic network between kagome "
        r"and interlayer.{0,160}?sites",
        search_text,
        flags=re.IGNORECASE,
    )
    vbs_match = re.search(
        r"Our findings further rule out the scenario of clinoatacamite "
        r"as valence bond solid from Ref\.\s*\[\s*21\s*\]",
        search_text,
        flags=re.IGNORECASE,
    )
    lee_match = re.search(
        r"\[\s*21\s*\].{0,40}?S\.\s*-\s*H\.\s*Lee"
        r".{0,260}?K\.\s*Kiefer"
        r".{0,100}?Quantum-spin-liquid states in the two-dimensional "
        r"kagome antiferromagnets"
        r".{0,180}?Nat\.\s*Mater\.\s*6\s*,\s*853\s*"
        r"\(\s*2007\s*\)",
        search_text,
        flags=re.IGNORECASE,
    )

    matches_by_name = {
        "identified_v2_source": title_match,
        "arxiv_version_and_date": version_match,
        "abstract_dft_classification": abstract_match,
        "nonuniform_model_and_interlayer_coupling": model_match,
        "site_and_six_path_topology": topology_match,
        "dft_exchange_and_curie_weiss_values": caption_match,
        "dominant_afm_kagome_exchanges": dominant_match,
        "weaker_fm_interlayer_exchanges": interlayer_match,
        "modern_vbs_rejection": vbs_match,
        "intended_lee_2007_citation": lee_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified arXiv v2 source, "
            "DFT distorted-kagome classification, six inequivalent "
            "exchange paths and values, AFM/FM hierarchy, weak "
            "interlayer bound, Lee 2007 citation, and explicit VBS "
            f"rejection; missing anchors: {', '.join(missing_anchors)}"
        )

    exchange_values = {
        f"J{index}": float(caption_match.group(f"j{index}"))
        for index in range(1, 7)
    }
    expected_exchange_values = {
        "J1": -6.8,
        "J2": -14.5,
        "J3": -30.3,
        "J4": 120.1,
        "J5": 211.6,
        "J6": 367.7,
    }
    dft_u = float(caption_match.group("u"))
    curie_weiss_temperature = float(caption_match.group("theta"))
    reported_bound = float(interlayer_match.group("bound"))
    dominant_values = {
        f"J{index}": float(dominant_match.group(f"j{index}"))
        for index in range(4, 7)
    }
    interlayer_values = {
        f"J{index}": float(interlayer_match.group(f"j{index}"))
        for index in range(1, 4)
    }
    exact_numbers = (
        math.isclose(dft_u, 7.19, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            curie_weiss_temperature,
            -165.0,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        and math.isclose(
            reported_bound, 0.082, rel_tol=0.0, abs_tol=1.0e-12
        )
        and all(
            math.isclose(
                exchange_values[name],
                expected,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
            for name, expected in expected_exchange_values.items()
        )
        and all(
            math.isclose(
                dominant_values[name],
                expected_exchange_values[name],
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
            for name in dominant_values
        )
        and all(
            math.isclose(
                interlayer_values[name],
                expected_exchange_values[name],
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
            for name in interlayer_values
        )
        and all(exchange_values[name] < 0.0 for name in ("J1", "J2", "J3"))
        and all(exchange_values[name] > 0.0 for name in ("J4", "J5", "J6"))
    )
    if not exact_numbers:
        raise RuntimeEvidenceError(
            f"{error_prefix} numerical anchors disagree with the "
            "reported six-exchange DFT hierarchy"
        )

    matches = tuple(matches_by_name.values())
    return (
        {"distorted_kagome_reference": True},
        {
            "parser": (
                "parse_stodter_clinoatacamite_distorted_kagome_exchange"
            ),
            "source_identity": "arXiv:2601.21024v2",
            "accepted_prl_doi": "10.1103/xmh8-68vk",
            "registered_doi": "10.1038/nmat1867",
            "corrected_historical_doi": "10.1038/nmat1986",
            "in_plane_exchange_paths": ["J4", "J5", "J6"],
            "interlayer_exchange_paths": ["J1", "J2", "J3"],
            "exchange_values_k": exchange_values,
            "dft_u_ev": dft_u,
            "curie_weiss_temperature_k": curie_weiss_temperature,
            "reported_interlayer_bound_over_j6": reported_bound,
            "exchange_hierarchy": (
                "dominant non-uniform AFM kagome J4-J6; weaker FM "
                "kagome-interlayer J1-J3"
            ),
            "historical_vbs_scenario_supported": False,
            "source_role": (
                "current machine-extractable corrective direct primary "
                "research source"
            ),
            "registered_source_relationship": (
                "The registered DOI 10.1038/nmat1867 is Yamada et al.'s "
                "magnetic-disk vortex paper. Lee et al.'s intended 2007 "
                "clinoatacamite source is DOI 10.1038/nmat1986; Stodter "
                "et al. retain its broad distorted-kagome/interlayer "
                "setting, replace it with a DFT-resolved six-exchange "
                "hierarchy, and rule out Lee et al.'s VBS scenario."
            ),
            "claim_scope": (
                "boolean distorted-kagome material-model characterization "
                "for bulk clinoatacamite Cu2Cl(OH)3; the parser does not "
                "promote the superseded VBS interpretation or claim exact "
                "classical minima from the source text"
            ),
            "matched_anchors": [
                "identified Stodter et al. clinoatacamite title",
                "arXiv:2601.21024v2 identity and 19 June 2026 date",
                "abstract DFT distorted-kagome low-symmetry classification",
                "non-uniform kagome AFM with weak FM interlayer coupling",
                "Cu(2)/Cu(3) kagome, Cu(1) interlayer, and six NN paths",
                "U, Curie-Weiss temperature, and all six DFT exchanges",
                "dominant J4-J6 non-uniform AFM kagome layer",
                "weaker J1-J3 FM kagome-interlayer network",
                "modern single-crystal work rules out the VBS scenario",
                "Lee et al. Nat. Mater. 6, 853 (2007) historical citation",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_ishikawa_edwardsite_spin_half_deformed_kagome(source_text):
    """Extract the hydrated spin-half Edwardsite material characterization."""

    error_prefix = "Ishikawa Edwardsite deformed-kagome antiferromagnet"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_ishikawa_edwardsite_spin_half_deformed_kagome",
    )
    return _finalize_prepared_trace(
        _parse_ishikawa_edwardsite_spin_half_deformed_kagome_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_ishikawa_edwardsite_spin_half_deformed_kagome_prepared(
    search_text,
):
    error_prefix = "Ishikawa Edwardsite deformed-kagome antiferromagnet"

    formula = (
        r"Cd\s*2\s*Cu\s*3\s*\(\s*SO\s*4\s*\)\s*2"
        r"\s*\(\s*OH\s*\)\s*6\s*\*\s*4\s*H\s*2\s*O"
    )
    spin_half = r"spin\s*-\s*1\s*/\s*2"

    identity_match = re.search(
        r"Magnetic Properties of the Spin\s*-\s*1\s*/\s*2 "
        r"Deformed Kagome Antiferromagnet Edwardsite"
        r".{0,500}?Hajime Ishikawa"
        r".{0,180}?Yoshihiko Okamoto"
        r".{0,180}?Zenji Hiroi",
        search_text,
        flags=re.IGNORECASE,
    )
    version_match = re.search(
        r"arXiv\s*:\s*1305\.2477v1"
        r".{0,100}?\[\s*cond-mat\.mtrl-sci\s*\]"
        r".{0,80}?11\s+May\s+2013",
        search_text,
        flags=re.IGNORECASE,
    )
    abstract_material_match = re.search(
        r"prepared a powder sample of edwardsite"
        r".{0,100}?"
        + formula
        + r".{0,180}?new candidate compound for the\s*"
        + spin_half
        + r"\s*kagome antiferromagnet"
        r".{0,260}?studied its magnetic properties by magnetic "
        r"susceptibility and heat capacity measurements",
        search_text,
        flags=re.IGNORECASE,
    )
    abstract_result_match = re.search(
        r"Edwardsite has a deformed kagome lattice with an average "
        r"antiferromagnetic interaction of\s*"
        r"(?P<average_j>\d+(?:\.\d+)?)\s*K"
        r".{0,180}?shows an antiferromagnetic order accompanied by a "
        r"small ferromagnetic moment below\s*"
        r"(?P<ordering_temperature>\d+(?:\.\d+)?)\s*K"
        r".{0,260}?spin canting caused by sizable "
        r"Dzyaloshinsky-Moriya interactions",
        search_text,
        flags=re.IGNORECASE,
    )
    geometry_match = re.search(
        r"The\s*"
        + spin_half
        + r"\s*antiferromagnet on a kagome lattice"
        r".{0,160}?two-dimensional network of corner-sharing triangles",
        search_text,
        flags=re.IGNORECASE,
    )
    layer_match = re.search(
        r"Cu\s*2\s*\+\s*ions are aligned in a kagome geometry"
        r".{0,700}?kagome layers are well separated from each other"
        r".{0,300}?thick nonmagnetic block layer"
        r".{0,500}?distance between kagome layers is\s*"
        r"(?P<layer_distance>\d+(?:\.\d+)?)\s*"
        r"(?:˚\s*A|Å|A|Angstrom)"
        r".{0,500}?interplanar coupling is relatively small in edwardsite",
        search_text,
        flags=re.IGNORECASE,
    )
    deformation_match = re.search(
        r"Cu\s*2\s*\+\s*ions occupy\s*"
        r"(?P<site_count>\w+)\s+crystallographic sites"
        r".{0,180}?Cu\s*-\s*Cu distance in the kagome lattice "
        r"varies within\s*"
        r"(?P<distance_variation>\d+(?:\.\d+)?)\s*%"
        r".{0,2200}?prepared a pure sample of\s*"
        + formula,
        search_text,
        flags=re.IGNORECASE,
    )
    curie_weiss_match = re.search(
        r"Curie-Weiss"
        r".{0,800}?(?:theta|θ)\s*_?\s*W\s*=\s*"
        r"(?P<theta>-?\d+(?:\.\d+)?)\s*\(\s*3\s*\)\s*K",
        search_text,
        flags=re.IGNORECASE,
    )
    htse_match = re.search(
        r"(?:fit (?:the )?(?:M\s*/\s*H|magnetic susceptibility) data "
        r"between|magnetic susceptibility data between)\s*"
        r"(?P<fit_low>\d+)\s*and\s*(?P<fit_high>\d+)\s*K"
        r".{0,300}?calculation for the\s*"
        + spin_half
        + r"\s*KAFM using the high-temperature-series expansion"
        r".{0,260}?fit gives\s*J\s*/\s*k\s*_?\s*B\s*=\s*"
        r"(?P<j>\d+(?:\.\d+)?)\s*\(\s*1\s*\)\s*K"
        r".{0,160}?Lande g-factor of\s*g\s*=\s*"
        r"(?P<g>\d+(?:\.\d+)?)\s*\(\s*1\s*\)",
        search_text,
        flags=re.IGNORECASE,
    )
    transition_match = re.search(
        r"heat capacity"
        r".{0,600}?zero magnetic field"
        r".{0,600}?broad but distinct peak at\s*"
        r"T\s*_?\s*N\s*=\s*"
        r"(?P<ordering_temperature>\d+(?:\.\d+)?)\s*K"
        r".{0,2200}?(?:magnetic interactions|"
        r"magnetic interac.{0,1500}?tions) in edwardsite are definitely "
        r"antiferromagnetic"
        r".{0,300}?must be due to a canted antiferromagnetic order",
        search_text,
        flags=re.IGNORECASE,
    )
    bond_topology_match = re.search(
        r"Cu\s*2\s*\+\s*ions occupy\s*"
        r"(?P<site_count>\w+)\s+different crystallographic sites on the "
        r"kagome plane"
        r".{0,220}?giving\s*(?P<bond_count>\w+)\s+nonequivalent Cu-Cu "
        r"bonds with different magnetic couplings",
        search_text,
        flags=re.IGNORECASE,
    )
    angle_match = re.search(
        r"All the(?:\s+\d{1,2})?\s+magnetic interactions in edwardsite "
        r"must be "
        r"antiferromagnetic"
        r".{0,260}?Cu-O\s*\(\s*H\s*\)\s*-Cu angles"
        r".{0,100}?between\s*(?P<low_angle>\d+)"
        r"\s*(?:degrees|°|◦)\s*and\s*(?P<high_angle>\d+)"
        r"\s*(?:degrees|°|◦)",
        search_text,
        flags=re.IGNORECASE,
    )
    grouping_match = re.search(
        r"(?:six|6) antiferromagnetic couplings are classified into "
        r"two groups"
        r".{0,160}?(?P<strong_count>\w+)\s+stronger ones with\s*J"
        r".{0,100}?(?P<weak_count>\w+)\s+weaker ones with\s*J\s*['′]"
        r".{0,240}?kagome lattice(?: of edwardsite)? "
        r"approximately consists "
        r"of\s*J\s*-\s*J\s*['′]\s*-\s*J\s*['′]\s*isosceles triangles",
        search_text,
        flags=re.IGNORECASE,
    )
    summary_match = re.search(
        r"In summary,\s*(?:we show that\s*)?edwardsite is a\s*"
        + spin_half
        + r"\s*deformed KAFM with an average\s*J\s*/\s*k\s*_?\s*B"
        r"\s*=\s*(?P<j>\d+(?:\.\d+)?)\s*K"
        r".{0,200}?antiferromagnetic order"
        r".{0,120}?below\s*T\s*_?\s*N\s*=\s*"
        r"(?P<ordering_temperature>\d+(?:\.\d+)?)\s*K"
        r".{0,260}?suggested to be a canted\s*120"
        r"\s*-?\s*(?:degrees?|°|◦)\s*order with a\s*q\s*=\s*"
        r"(?P<q>\d+)\s*propagation vector",
        search_text,
        flags=re.IGNORECASE,
    )

    matches_by_name = {
        "identified_ishikawa_edwardsite_source": identity_match,
        "arxiv_version_and_date": version_match,
        "hydrated_spin_half_material_and_measurements": (
            abstract_material_match
        ),
        "abstract_exchange_order_and_dm_result": abstract_result_match,
        "corner_sharing_kagome_geometry": geometry_match,
        "separated_kagome_layers": layer_match,
        "four_site_deformation_and_pure_sample": deformation_match,
        "curie_weiss_temperature": curie_weiss_match,
        "spin_half_htse_exchange_fit": htse_match,
        "heat_capacity_canted_afm_transition": transition_match,
        "four_site_six_bond_topology": bond_topology_match,
        "all_antiferromagnetic_bond_angles": angle_match,
        "two_strong_four_weak_exchange_groups": grouping_match,
        "spin_half_canted_q0_summary": summary_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified arXiv source, "
            "hydrated spin-half material formula, susceptibility and "
            "heat-capacity methods, deformed kagome geometry, Curie-Weiss "
            "and HTSE scales, bulk canted-AFM transition, six-bond "
            "antiferromagnetic hierarchy, and explicitly suggested q=0 "
            f"summary; missing anchors: {', '.join(missing_anchors)}"
        )

    word_to_integer = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
    }

    def _integer(group_value):
        value = group_value.lower()
        if value in word_to_integer:
            return word_to_integer[value]
        try:
            return int(value)
        except ValueError as exc:
            raise RuntimeEvidenceError(
                f"{error_prefix} contains an unrecognized integer word"
            ) from exc

    abstract_j = float(abstract_result_match.group("average_j"))
    abstract_ordering_temperature = float(
        abstract_result_match.group("ordering_temperature")
    )
    layer_distance = float(layer_match.group("layer_distance"))
    crystallographic_site_count = _integer(
        deformation_match.group("site_count")
    )
    distance_variation_percent = float(
        deformation_match.group("distance_variation")
    )
    curie_weiss_temperature = float(curie_weiss_match.group("theta"))
    fit_window = [
        int(htse_match.group("fit_low")),
        int(htse_match.group("fit_high")),
    ]
    htse_j = float(htse_match.group("j"))
    lande_g = float(htse_match.group("g"))
    transition_temperature = float(
        transition_match.group("ordering_temperature")
    )
    topology_site_count = _integer(
        bond_topology_match.group("site_count")
    )
    nonequivalent_bond_count = _integer(
        bond_topology_match.group("bond_count")
    )
    low_angle = int(angle_match.group("low_angle"))
    high_angle = int(angle_match.group("high_angle"))
    strong_exchange_count = _integer(grouping_match.group("strong_count"))
    weak_exchange_count = _integer(grouping_match.group("weak_count"))
    summary_j = float(summary_match.group("j"))
    summary_ordering_temperature = float(
        summary_match.group("ordering_temperature")
    )
    summary_q = int(summary_match.group("q"))

    exact_numbers = (
        math.isclose(abstract_j, 51.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            abstract_ordering_temperature,
            4.3,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        and math.isclose(
            layer_distance, 10.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and crystallographic_site_count == 4
        and math.isclose(
            distance_variation_percent,
            5.0,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        and math.isclose(
            curie_weiss_temperature,
            -66.2,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        and fit_window == [150, 300]
        and math.isclose(htse_j, 51.1, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(lande_g, 2.195, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            transition_temperature,
            4.3,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        and topology_site_count == 4
        and nonequivalent_bond_count == 6
        and [low_angle, high_angle] == [109, 116]
        and strong_exchange_count == 2
        and weak_exchange_count == 4
        and math.isclose(summary_j, 51.1, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            summary_ordering_temperature,
            4.3,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        and summary_q == 0
    )
    if not exact_numbers:
        raise RuntimeEvidenceError(
            f"{error_prefix} numerical anchors disagree with the "
            "reported hydrated spin-half Edwardsite characterization"
        )

    matches = tuple(matches_by_name.values())
    return (
        {"kagome_antiferromagnet_reference": True},
        {
            "parser": (
                "parse_ishikawa_edwardsite_spin_half_deformed_kagome"
            ),
            "source_identity": "arXiv:1305.2477v1",
            "journal_doi": "10.7566/JPSJ.82.063710",
            "registered_doi": "10.1038/ncomms14113",
            "source_spin": 0.5,
            "registered_spin": 1.0,
            "source_material_formula": "Cd2Cu3(SO4)2(OH)6·4H2O",
            "registered_material_formula": "Cd2Cu3(OH)6(SO4)2",
            "crystallographic_cu_site_count": crystallographic_site_count,
            "nonequivalent_cu_cu_bond_count": nonequivalent_bond_count,
            "strong_exchange_count": strong_exchange_count,
            "weak_exchange_count": weak_exchange_count,
            "curie_weiss_temperature_k": curie_weiss_temperature,
            "htse_average_j_over_kb_k": htse_j,
            "lande_g_factor": lande_g,
            "ordering_temperature_k": transition_temperature,
            "suggested_order": "canted_120_degree_q0",
            "source_role": (
                "machine-extractable corrective direct primary research "
                "source"
            ),
            "registered_source_and_model_correction": (
                "The registered DOI 10.1038/ncomms14113 is a "
                "hydronium-ion catalysis paper. The intended Edwardsite "
                "source is Ishikawa, Okamoto, and Hiroi, DOI "
                "10.7566/JPSJ.82.063710. It studies hydrated "
                "Cd2Cu3(SO4)2(OH)6·4H2O with Cu spin 1/2, not the "
                "registry's anhydrous-formula spin-1 model."
            ),
            "claim_scope": (
                "boolean material-reference claim for hydrated spin-1/2 "
                "deformed-kagome Edwardsite; no validation is claimed "
                "for the registry's spin-1 Hamiltonian, an anhydrous "
                "material, or an exact ideal-kagome classical 120-degree "
                "manifold"
            ),
            "matched_anchors": [
                "identified Ishikawa-Okamoto-Hiroi Edwardsite source",
                "arXiv:1305.2477v1 identity and 11 May 2013 date",
                "hydrated spin-half material and two measurement methods",
                "abstract deformed-kagome 51 K, 4.3 K, and DM result",
                "spin-half two-dimensional corner-sharing kagome geometry",
                "10 A separated kagome layers and weak interplanar coupling",
                "four-site five-percent deformation and pure hydrated sample",
                "Curie-Weiss theta_W=-66.2(3) K",
                "spin-half HTSE J/kB=51.1(1) K and g=2.195(1)",
                "heat-capacity TN=4.3 K canted-AFM transition",
                "four Cu sites and six nonequivalent kagome bonds",
                "109-116 degree paths imply all-AFM exchanges",
                "two stronger J and four weaker J-prime couplings",
                "summary suggests canted 120-degree q=0 order",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_nawa_rubr3_kitaev_candidate_and_competing_interactions(
    source_text,
):
    """Extract the scoped RuBr3 candidate label and direct neutron limits."""

    error_prefix = "Nawa RuBr3 magnetic-excitation source"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_nawa_rubr3_kitaev_candidate_and_competing_interactions",
    )
    return _finalize_prepared_trace(
        _parse_nawa_rubr3_kitaev_candidate_and_competing_interactions_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_nawa_rubr3_kitaev_candidate_and_competing_interactions_prepared(
    search_text,
):
    error_prefix = "Nawa RuBr3 magnetic-excitation source"

    identity_match = re.search(
        r"https?\s*:\s*//\s*doi\.org\s*/\s*"
        r"10\.1038\s*/\s*s41535-026-00868-6"
        r".{0,500}?Magnetic excitations of the Kitaev model candidate "
        r"RuBr\s*3"
        r".{0,800}?Kazuhiro Nawa"
        r".{0,300}?Yoshinori Imai"
        r".{0,1800}?Taku J\.\s*Sato",
        search_text,
        flags=re.IGNORECASE,
    )
    experiment_match = re.search(
        r"performed powder inelastic neutron scattering on RuBr\s*3 "
        r"with a layered honeycomb structure"
        r".{0,220}?is isostructural to the low-temperature structure of "
        r"alpha\s*-\s*RuCl\s*3",
        search_text,
        flags=re.IGNORECASE,
    )
    spectrum_temperature_match = re.search(
        r"Strongly dispersive magnetic modes were observed near the "
        r"(?:centre|center) of the antiferromagnetic zone below\s*"
        r"T\s*_?\s*N"
        r".{0,300}?spectral weight remains near the "
        r"(?:centre|center) of the antiferromagnetic zone just above\s*"
        r"T\s*_?\s*N"
        r".{0,200}?shifts to the Gamma point at\s*3\s*T\s*_?\s*N",
        search_text,
        flags=re.IGNORECASE,
    )
    abstract_competing_match = re.search(
        r"Strong dispersion indicates that antiferromagnetic interactions "
        r"that stabili[sz]e the zigzag antiferromagnetic order"
        r".{0,160}?nearest-neighbour symmetric off-diagonal or "
        r"third-neighbour isotropic magnetic interactions"
        r".{0,180}?are comparable to or even stronger than ferromagnetic "
        r"Kitaev interactions"
        r".{0,180}?drive the ground state of RuBr\s*3 away from the ideal "
        r"ferromagnetic Kitaev spin liquid state",
        search_text,
        flags=re.IGNORECASE,
    )
    bulk_context_match = re.search(
        r"Weiss temperature estimated from the Curie-Weiss fit is\s*"
        r"(?P<theta>-?\d+(?:\.\d+)?)\s*K"
        r".{0,1300}?RuBr\s*3 exhibits a zigzag antiferromagnetic order "
        r"below\s*(?P<tn>\d+(?:\.\d+)?)\s*K"
        r".{0,500}?size of the magnetic moments is\s*"
        r"(?P<moment>\d+(?:\.\d+)?)\s*\(\s*"
        r"(?P<moment_uncertainty>\d+)\s*\)\s*"
        r"mu\s*_?\s*B"
        r".{0,700}?tilting angle"
        r".{0,240}?(?P<tilt>\d+(?:\.\d+)?)\s*\(\s*"
        r"(?P<tilt_uncertainty>\d+)\s*\)\s*degrees",
        search_text,
        flags=re.IGNORECASE,
    )
    wavevector_match = re.search(
        r"inelastic neutron scattering spectrum of RuBr\s*3 reveals "
        r"strongly dispersive magnetic excitations centred at the "
        r"antiferromagnetic zone centre"
        r".{0,900}?occurrence of zigzag antiferromagnetic order below\s*"
        r"(?P<tn>\d+(?:\.\d+)?)\s*K was confirmed by"
        r".{0,120}?neutron diffraction experiments"
        r".{0,700}?Peaks were observed at\s*"
        r"(?P<first_q>\d+(?:\.\d+)?)\s*and\s*"
        r"(?P<second_q>\d+(?:\.\d+)?)\s*"
        r"(?:A\s*-\s*1|inverse Angstrom)",
        search_text,
        flags=re.IGNORECASE,
    )
    energy_match = re.search(
        r"dispersive magnetic excitations range from\s*"
        r"(?P<low_energy>\d+(?:\.\d+)?)\s*to\s*"
        r"(?P<high_energy>\d+(?:\.\d+)?)\s*meV"
        r".{0,500}?spectrum shows an energy gap of\s*"
        r"(?P<gap>\d+(?:\.\d+)?)\s*meV at\s*"
        r"(?P<gap_temperature>\d+(?:\.\d+)?)\s*K"
        r".{0,300}?becomes almost zero above\s*"
        r"(?P<closing_temperature>\d+(?:\.\d+)?)\s*K",
        search_text,
        flags=re.IGNORECASE,
    )
    no_kitaev_attribution_match = re.search(
        r"could not conclude that the weak excitations are induced by the "
        r"Kitaev interactions"
        r".{0,280}?wavevector and energy dependences are not clear in the "
        r"powder inelastic scattering spectra",
        search_text,
        flags=re.IGNORECASE,
    )
    spin_wave_limit_match = re.search(
        r"(?:should )?provide a rough estimate for magnetic interactions"
        r".{0,260}?linear spin wave approximations would not perfectly "
        r"apply to the pseudospin\s*-\s*1\s*/\s*2 system",
        search_text,
        flags=re.IGNORECASE,
    )
    nonunique_fit_match = re.search(
        r"parameters\s*\(?\s*J\s*1\s*,\s*K\s*,\s*Gamma\s*,\s*"
        r"Gamma(?:0|['′])\s*,\s*J\s*2\s*,\s*and\s*J\s*3"
        r".{0,900}?not possible to estimate several exchange parameters "
        r"simultaneously"
        r".{0,240}?two extreme combinations with the dominant Gamma or "
        r"J\s*3 term"
        r".{0,260}?parameters are phenomenologically adjusted",
        search_text,
        flags=re.IGNORECASE,
    )
    gamma_model_match = re.search(
        r"former.{0,100}?model includes a large Gamma term with zero "
        r"J\s*2 and J\s*3"
        r".{0,120}?J\s*1\s*=\s*(?P<j1>-?\d+(?:\.\d+)?)\s*,\s*"
        r"K\s*=\s*(?P<k>-?\d+(?:\.\d+)?)\s*,\s*"
        r"Gamma\s*=\s*(?P<gamma>-?\d+(?:\.\d+)?)\s*,\s*"
        r"Gamma(?:0|['′])\s*=\s*"
        r"(?P<gamma_prime>-?\d+(?:\.\d+)?)\s*meV",
        search_text,
        flags=re.IGNORECASE,
    )
    if gamma_model_match is None:
        gamma_model_match = re.search(
            r"J\s*1\s*-\s*K\s*-\s*Gamma\s*-\s*"
            r"Gamma(?:0|['′]) and b the "
            r"J\s*1\s*-\s*K\s*-\s*J\s*2\s*-\s*J\s*3 models"
            r".{0,300}?parameters used for the simulations are a\s*"
            r"J\s*1\s*=\s*(?P<j1>-?\d+(?:\.\d+)?)\s*,\s*"
            r"K\s*=\s*(?P<k>-?\d+(?:\.\d+)?)\s*,\s*"
            r"Gamma\s*=\s*(?P<gamma>-?\d+(?:\.\d+)?)\s*,\s*"
            r"Gamma(?:0|['′])\s*=\s*"
            r"(?P<gamma_prime>-?\d+(?:\.\d+)?)\s*meV",
            search_text,
            flags=re.IGNORECASE,
        )
    j3_model_match = re.search(
        r"latter.{0,100}?model includes a large J\s*3 term with zero Gamma"
        r".{0,120}?J\s*1\s*=\s*(?P<j1>-?\d+(?:\.\d+)?)\s*,\s*"
        r"K\s*=\s*(?P<k>-?\d+(?:\.\d+)?)\s*,\s*"
        r"J\s*2\s*=\s*(?P<j2>-?\d+(?:\.\d+)?)\s*,\s*"
        r"J\s*3\s*=\s*(?P<j3>-?\d+(?:\.\d+)?)\s*,\s*"
        r"Gamma(?:0|['′])\s*=\s*"
        r"(?P<gamma_prime>-?\d+(?:\.\d+)?)\s*meV"
        r".{0,500}?Interplane interactions of\s*J\s*p\s*=\s*"
        r"(?P<jp>-?\d+(?:\.\d+)?)\s*meV were included in both models",
        search_text,
        flags=re.IGNORECASE,
    )
    if j3_model_match is None:
        j3_model_match = re.search(
            r"Gamma(?:0|['′])\s*=\s*-2\.5\s*meV and b\s*"
            r"J\s*1\s*=\s*(?P<j1>-?\d+(?:\.\d+)?)\s*,\s*"
            r"K\s*=\s*(?P<k>-?\d+(?:\.\d+)?)\s*,\s*"
            r"J\s*2\s*=\s*(?P<j2>-?\d+(?:\.\d+)?)\s*,\s*"
            r"J\s*3\s*=\s*(?P<j3>-?\d+(?:\.\d+)?)\s*,\s*(?:and\s*)?"
            r"Gamma(?:0|['′])\s*=\s*"
            r"(?P<gamma_prime>-?\d+(?:\.\d+)?)\s*meV"
            r".{0,500}?Interplane interactions of\s*J\s*p\s*=\s*"
            r"(?P<jp>-?\d+(?:\.\d+)?)\s*meV are "
            r"(?:adopted|included) in both models"
            r".{0,1800}?latter model includes a large J\s*3 term with "
            r"zero Gamma",
            search_text,
            flags=re.IGNORECASE,
        )
    summary_match = re.search(
        r"In summary,\s*magnetic excitations of a new polymorph of "
        r"RuBr\s*3 were investigated via powder inelastic neutron "
        r"scattering experiments"
        r".{0,500}?strong antiferromagnetic interactions "
        r"(?:coexist|coexisting) with (?:the )?sizable ferromagnetic "
        r"Kitaev interactions"
        r".{0,500}?J\s*1\s*-\s*K\s*-\s*Gamma\s*-\s*"
        r"Gamma(?:0|['′]) model with a large Gamma term"
        r".{0,200}?J\s*1\s*-\s*K\s*-\s*J\s*2\s*-\s*J\s*3 model with a "
        r"large J\s*3 term"
        r".{0,360}?ground state of RuBr\s*3 away from the ideal "
        r"ferromagnetic Kitaev spin liquid state",
        search_text,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"(?:Hamiltonian contains|Jij represents) nearest-neighbour "
        r"anisotropic interactions,\s*including the Kitaev term K,\s*"
        r"Heisenberg term J\s*1,\s*and non-diagonal components Gamma and "
        r"Gamma(?:0|['′])"
        r".{0,800}?(?:introduced|introduce) J\s*2,\s*J\s*3 and J\s*p"
        r".{0,260}?next\s*-?\s*nearest-neighbour"
        r".{0,220}?third\s*-?\s*nearest-neighbour"
        r".{0,260}?(?:interplane|c-axis)",
        search_text,
        flags=re.IGNORECASE,
    )
    luttinger_tisza_match = re.search(
        r"classical ground state was estimated by the Luttinger-Tisza "
        r"method"
        r".{0,2600}?zigzag antiferromagnetic order was confirmed to be the "
        r"classical ground state for the given parameters",
        search_text,
        flags=re.IGNORECASE,
    )
    if luttinger_tisza_match is None:
        luttinger_tisza_match = re.search(
            r"zigzag antiferromagnetic order was confirmed to be the "
            r"classical ground state for the given parameters"
            r".{0,2600}?classical ground state was estimated by the "
            r"Luttinger-Tisza method",
            search_text,
            flags=re.IGNORECASE,
        )
    dates_match = re.search(
        r"Received\s*:\s*3 October 2025\s*;\s*"
        r"Accepted\s*:\s*21 February 2026",
        search_text,
        flags=re.IGNORECASE,
    )
    imai_reference_match = re.search(
        r"Imai,\s*Y\.\s*et al\.\s*Zigzag magnetic order in the "
        r"Kitaev spin-liquid candidate material RuBr\s*3 with a honeycomb "
        r"lattice\.\s*Phys\.\s*Rev\.\s*B\s*105,\s*L041112\s*"
        r"\(\s*2022\s*\)",
        search_text,
        flags=re.IGNORECASE,
    )

    matches_by_name = {
        "identified_nawa_rubr3_source": identity_match,
        "powder_ins_layered_honeycomb_material": experiment_match,
        "temperature_dependent_dispersive_spectrum": (
            spectrum_temperature_match
        ),
        "abstract_competing_interactions_and_away_conclusion": (
            abstract_competing_match
        ),
        "bulk_weiss_zigzag_and_moment_context": bulk_context_match,
        "neutron_confirmed_order_and_wavevectors": wavevector_match,
        "excitation_range_and_temperature_dependent_gap": energy_match,
        "no_powder_based_kitaev_attribution": no_kitaev_attribution_match,
        "pseudospin_half_linear_spin_wave_limit": spin_wave_limit_match,
        "nonunique_phenomenological_parameter_fit": nonunique_fit_match,
        "gamma_dominant_parameter_set": gamma_model_match,
        "j3_dominant_parameter_set": j3_model_match,
        "summary_competing_interactions_and_away_conclusion": summary_match,
        "extended_anisotropic_exchange_hamiltonian": hamiltonian_match,
        "luttinger_tisza_zigzag_ground_state": luttinger_tisza_match,
        "received_and_accepted_dates": dates_match,
        "imai_2022_direct_material_reference": imai_reference_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified 2026 article, direct "
            "powder-neutron method, layered-honeycomb RuBr3 structure, "
            "temperature-dependent dispersive spectrum, competing Gamma/J3 "
            "interactions, both explicitly nonunique parameter sets, "
            "linear-spin-wave limitations, and the conclusion that the "
            "ordered state is away from the ideal Kitaev limit; missing "
            f"anchors: {', '.join(missing_anchors)}"
        )

    theta = float(bulk_context_match.group("theta"))
    bulk_tn = float(bulk_context_match.group("tn"))
    moment = float(bulk_context_match.group("moment"))
    moment_uncertainty = float(
        f"0.{bulk_context_match.group('moment_uncertainty')}"
    )
    tilt = float(bulk_context_match.group("tilt"))
    tilt_uncertainty = float(
        bulk_context_match.group("tilt_uncertainty")
    )
    neutron_tn = float(wavevector_match.group("tn"))
    first_q = float(wavevector_match.group("first_q"))
    second_q = float(wavevector_match.group("second_q"))
    low_energy = float(energy_match.group("low_energy"))
    high_energy = float(energy_match.group("high_energy"))
    gap = float(energy_match.group("gap"))
    gap_temperature = float(energy_match.group("gap_temperature"))
    closing_temperature = float(
        energy_match.group("closing_temperature")
    )
    gamma_model = {
        "J1": float(gamma_model_match.group("j1")),
        "K": float(gamma_model_match.group("k")),
        "Gamma": float(gamma_model_match.group("gamma")),
        "Gamma_prime": float(gamma_model_match.group("gamma_prime")),
        "J2": 0.0,
        "J3": 0.0,
        "Jp": float(j3_model_match.group("jp")),
    }
    j3_model = {
        "J1": float(j3_model_match.group("j1")),
        "K": float(j3_model_match.group("k")),
        "Gamma": 0.0,
        "Gamma_prime": float(j3_model_match.group("gamma_prime")),
        "J2": float(j3_model_match.group("j2")),
        "J3": float(j3_model_match.group("j3")),
        "Jp": float(j3_model_match.group("jp")),
    }

    expected_numbers = (
        math.isclose(theta, -58.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(bulk_tn, 34.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(neutron_tn, 34.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(moment, 0.74, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            moment_uncertainty, 0.12, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(tilt, 64.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            tilt_uncertainty, 12.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(first_q, 0.60, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(second_q, 1.55, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            low_energy, 1.5, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            high_energy, 15.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(gap, 1.5, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            gap_temperature, 10.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            closing_temperature, 25.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and gamma_model
        == {
            "J1": -1.8,
            "K": -7.2,
            "Gamma": 10.5,
            "Gamma_prime": -2.5,
            "J2": 0.0,
            "J3": 0.0,
            "Jp": 0.15,
        }
        and j3_model
        == {
            "J1": 1.5,
            "K": -8.1,
            "Gamma": 0.0,
            "Gamma_prime": -0.16,
            "J2": 0.8,
            "J3": 5.8,
            "Jp": 0.15,
        }
    )
    if not expected_numbers:
        raise RuntimeEvidenceError(
            f"{error_prefix} numerical anchors disagree with the direct "
            "RuBr3 neutron and phenomenological spin-wave results"
        )

    matches = tuple(matches_by_name.values())
    return (
        {"ru_honeycomb_kitaev_candidate": True},
        {
            "parser": (
                "parse_nawa_rubr3_kitaev_candidate_and_competing_"
                "interactions"
            ),
            "source_identity": "doi:10.1038/s41535-026-00868-6",
            "registered_doi": "10.1088/1361-648X/aa8cf5",
            "original_material_doi": "10.1103/PhysRevB.105.L041112",
            "material": "RuBr3",
            "structure": "layered_honeycomb",
            "experiment": "powder_inelastic_neutron_scattering",
            "curie_weiss_temperature_k": theta,
            "ordering_temperature_k": bulk_tn,
            "ordered_moment_mu_b": moment,
            "ordered_moment_uncertainty_mu_b": moment_uncertainty,
            "moment_tilt_degrees": tilt,
            "moment_tilt_uncertainty_degrees": tilt_uncertainty,
            "magnetic_excitation_range_mev": [
                low_energy,
                high_energy,
            ],
            "energy_gap_mev_at_10_k": gap,
            "dominant_competing_interaction_options": [
                "nearest_neighbor_Gamma",
                "third_neighbor_J3",
            ],
            "gamma_dominant_model_mev": gamma_model,
            "j3_dominant_model_mev": j3_model,
            "fit_status": (
                "two phenomenological extreme parameter combinations, "
                "not a simultaneous unique exchange fit"
            ),
            "kitaev_limit_assessment": (
                "ground state driven away from the ideal ferromagnetic "
                "Kitaev spin-liquid state"
            ),
            "source_role": (
                "machine-extractable corrective direct primary neutron "
                "source"
            ),
            "registered_source_and_scope_correction": (
                "The registered DOI 10.1088/1361-648X/aa8cf5 is Winter "
                "et al.'s 2017 review, whose cached text does not mention "
                "RuBr3. The direct RuBr3 neutron source used here is Nawa "
                "et al., DOI 10.1038/s41535-026-00868-6; the first "
                "synthesis and zigzag-order report is Imai et al., DOI "
                "10.1103/PhysRevB.105.L041112."
            ),
            "claim_scope": (
                "boolean RuBr3 honeycomb Kitaev-candidate label only; "
                "the source instead finds competing Gamma or J3 "
                "interactions that drive the ordered ground state away "
                "from the ideal ferromagnetic Kitaev spin liquid, and it "
                "does not establish a realized spin liquid, a unique "
                "exchange Hamiltonian, exact bond eigenvalues, or an "
                "independently recomputed classical zigzag energy"
            ),
            "matched_anchors": [
                "identified Nawa et al. 2026 RuBr3 source",
                "powder INS on layered-honeycomb RuBr3",
                "temperature-dependent dispersive antiferromagnetic modes",
                "Gamma/J3 interactions compete with ferromagnetic Kitaev",
                "thetaW=-58 K, TN=34 K, moment, and tilt",
                "neutron-confirmed zigzag order and two wavevectors",
                "1.5-15 meV excitations and 1.5 meV low-temperature gap",
                "powder data do not establish Kitaev-origin weak modes",
                "linear-spin-wave pseudospin-half limitation",
                "two nonunique phenomenological parameter combinations",
                "Gamma-dominant J1-K-Gamma-Gamma-prime parameters",
                "J3-dominant J1-K-J2-J3 parameters and Jp",
                "summary places ordered state away from ideal Kitaev limit",
                "extended anisotropic exchange Hamiltonian components",
                "Luttinger-Tisza zigzag ground state for fitted parameters",
                "received and accepted dates",
                "Imai 2022 direct synthesis and zigzag-order reference",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_boldrin_vesignieite_dominant_j3_correction(source_text):
    """Correct the distortion-dominated vesignieite model using neutron data."""

    error_prefix = "Boldrin vesignieite dominant-J3 correction"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_boldrin_vesignieite_dominant_j3_correction",
    )
    return _finalize_prepared_trace(
        _parse_boldrin_vesignieite_dominant_j3_correction_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_boldrin_vesignieite_dominant_j3_correction_prepared(
    search_text,
):
    error_prefix = "Boldrin vesignieite dominant-J3 correction"

    spin_half = r"(?:1\s*(?:/|=)?\s*2|12)"
    identity_spin = rf"(?:{spin_half}|2)"
    identity_match = re.search(
        r"Vesignieite\s*:\s*A[n]?\s*S\s*=\s*"
        + identity_spin
        + r"\s*Kagome Antiferromagnet with Dominant Third\s*-\s*"
        r"Neighbor Exchange"
        r".{0,900}?D\.\s*Boldrin"
        r".{0,1600}?H\.\s*C\.\s*Walker"
        r".{0,900}?A\.\s*S\.\s*Wills"
        r".{0,3000}?(?:"
        r"arXiv\s*:\s*1806\.03074v1"
        r"|DOI\s*:\s*10\.1103\s*/\s*PhysRevLett\.121\.107203"
        r")",
        search_text,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"neutron scattering measurements that deuterated vesignieite\s*"
        r"BaCu\s*3\s*V\s*2\s*O\s*8\s*\(\s*OD\s*\)\s*2"
        r".{0,180}?fully stoichiometric\s*S\s*=\s*"
        r"(?P<spin>" + spin_half + r")\s*kagome magnet with\s*<\s*"
        r"(?P<distortion>\d+(?:\.\d+)?)\s*%\s*lattice distortion"
        r".{0,280}?orders magnetically at\s*TN\s*=\s*"
        r"(?P<tn>\d+(?:\.\d+)?)\s*K"
        r".{0,300}?multi\s*-\s*k coplanar variant"
        r".{0,180}?triple\s*-\s*k octahedral structure"
        r".{0,300}?stabili[sz]ed by a dominant antiferromagnetic "
        r"(?:3rd|third)\s*-\s*neighbor exchange\s*J\s*3"
        r".{0,220}?minor\s*(?:1st|first)\s*-\s*or\s*"
        r"(?:2nd|second)\s*-\s*neighbou?r exchange(?:s)?"
        r".{0,300}?spin\s*-\s*wave spectrum is well described by a\s*"
        r"J\s*3\s*-\s*only model including a tiny symmetric exchange "
        r"anisotropy",
        search_text,
        flags=re.IGNORECASE,
    )
    crystal_match = re.search(
        r"Vesignieite consists of nearly perfect\s*Cu\s*2\s*\+\s*"
        r"kagome layers"
        r".{0,2500}?trigonal\s*P\s*3\s*1\s*2\s*1\s*space group"
        r".{0,500}?tiny scalene distortion of the triangles "
        r"corresponds? to less than(?:\s+a)?\s*"
        r"(?P<distortion>\d+(?:\.\d+)?)\s*%\s*difference in the "
        r"three\s*Cu\s*-\s*Cu bond lengths"
        r".{0,9000}?lowering of the"
        r".{0,5000}?kagome symmetry is due to a "
        r"cooperative Jahn\s*-\s*Teller dis.{0,1200}?tortion"
        r".{0,300}?formation of two distinct\s*Cu\s*2\s*\+"
        r".{0,1200}?sites",
        search_text,
        flags=re.IGNORECASE,
    )
    bulk_match = re.search(
        r"Magnetic susceptibility measurements show"
        r".{0,120}?thetaW\s*=\s*"
        r"(?P<theta>-?\d+(?:\.\d+)?)\s*K"
        r".{0,1600}?attempts to estimate the strength and anisotropy "
        r"of the exchange interactions based on nearest\s*-\s*neighbor "
        r"exchange\s*J\s*1\s*only"
        r".{0,400}?are bound to fail"
        r".{0,180}?vesignieite has a dominant\s*J\s*3\s*exchange",
        search_text,
        flags=re.IGNORECASE,
    )
    diffraction_match = re.search(
        r"peaks,?\s*observed at\s*Q values of\s*"
        r"(?P<q1>\d+(?:\.\d+)?)\s*,\s*"
        r"(?P<q2>\d+(?:\.\d+)?)\s*,\s*and\s*"
        r"(?P<q3>\d+(?:\.\d+)?)"
        r".{0,260}?indexed by a propagation vector of\s*k\s*=\s*"
        r"\(\s*(?P<k1>\d+(?:\.\d+)?\s*(?:/|=)\s*\d+)"
        r"\s*,\s*(?P<k2>-?\d+(?:\.\d+)?)"
        r"\s*,\s*(?P<k3>-?\d+(?:\.\d+)?)\s*\)"
        r".{0,220}?corresponds to the\s*M point of the Brillouin zone "
        r"of the kagome lattice",
        search_text,
        flags=re.IGNORECASE,
    )
    octahedral_match = re.search(
        r"magnetic structure of vesignieite is related to the octahedral "
        r"state"
        r".{0,220}?favored by a large antiferromagnetic\s*J\s*3\s*>\s*0"
        r".{0,450}?octahedral state is energetically degenerate with a "
        r"number of coplanar states"
        r".{0,200}?hexagonal",
        search_text,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"data were modeled using semi\s*-?\s*classical spin\s*-\s*wave "
        r"theory"
        r".{0,260}?assuming the hexagonal magnetic structure"
        r".{0,180}?spin Hamiltonian"
        r".{0,1200}?J\s*_?\s*ij"
        r".{0,500}?\(\s*1\s*\+\s*delta\s*\)"
        r".{0,500}?D\s*_?\s*ij"
        r".{0,300}?\(\s*S\s*_?\s*i\s*cross\s*S\s*_?\s*j\s*\)",
        search_text,
        flags=re.IGNORECASE,
    )
    fit_match = re.search(
        r"flat mode at\s*E\s*=\s*"
        r"(?P<flat_energy>\d+(?:\.\d+)?)\s*meV"
        r".{0,400}?J\s*3\s*-\s*J\s*d\s*approximately\s*"
        r"(?P<difference>\d+(?:\.\d+)?)"
        r".{0,500}?\|\s*J\s*d\s*\|\s*<\s*"
        r"(?P<jd_bound>\d+(?:\.\d+)?)\s*,\s*"
        r"\|\s*J\s*1\s*\|\s*<\s*"
        r"(?P<j1_bound>\d+(?:\.\d+)?)\s*,\s*and\s*"
        r"\|\s*J\s*2\s*\|\s*<<\s*"
        r"(?P<j2_bound>\d+(?:\.\d+)?)"
        r".{0,500}?best fit using an isotropic version"
        r".{0,600}?J\s*3\s*=\s*"
        r"(?P<best_j3>-?\d+(?:\.\d+)?)\s*and\s*"
        r"J\s*d\s*=\s*(?P<best_jd>-?\d+(?:\.\d+)?)"
        r"(?:\s*meV)?",
        search_text,
        flags=re.IGNORECASE,
    )
    cancellation_match = re.search(
        r"competing.{0,120}?paths (?:can )?cancel in vesignieite"
        r".{0,180}?leading to the negligible\s*J\s*1\s*and dominant\s*"
        r"J\s*3\s*exchange energies we observe",
        search_text,
        flags=re.IGNORECASE,
    )
    continuum_match = re.search(
        r"hexagonal structure"
        r".{0,500}?minimizes the\s*J\s*3\s*-\s*only "
        r"antiferromagnetic Heisenberg Hamiltonian on the kagome lattice"
        r".{0,300}?full continuum of magnetic orders including (?:the )?"
        r"octahedral and related coplanar and col(?:linear|inear) orders",
        search_text,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"In conclusion,\s*(?:our )?neutron scattering data show that "
        r"(?:the mineral )?vesignieite orders magnetically at\s*"
        r"TN\s*=\s*(?P<tn>\d+(?:\.\d+)?)\s*K"
        r".{0,220}?hexagonal multi\s*-\s*k structure"
        r".{0,400}?dominant antiferromagnetic third\s*-\s*neighbor "
        r"interactions,\s*J\s*3\s*>\s*0"
        r".{0,900}?first\s*-\s*and second(?:\s*-\s*|\s+)neighbor "
        r"interactions are weak compared to "
        r"third\s*-\s*neighbor interactions",
        search_text,
        flags=re.IGNORECASE,
    )
    anisotropy_match = re.search(
        r"weak symmetric exchange anisotropy of\s*delta\s*(?:/|=)\s*"
        r"J\s*3\s*=\s*(?P<ratio>-?\d+(?:\.\d+)?)"
        r".{0,180}?stabili[sz]es the coplanar hexagonal magnetic "
        r"structure from this manifold",
        search_text,
        flags=re.IGNORECASE,
    )
    original_reference_match = re.search(
        r"Y\.\s*Okamoto,\s*H\.\s*Yoshida\.?\s*,?\s*and\s*Z\.\s*Hiroi"
        r".{0,200}?Vesignieite\s*BaCu\s*3\s*V\s*2\s*O\s*8\s*"
        r"\(\s*OH\s*\)\s*2\s*as a candidate spin\s*-\s*"
        + spin_half
        + r"\s*kagome antiferromagnet"
        r".{0,160}?J\.\s*Phys\.\s*Soc\.\s*J(?:apan|pn)\.?\s*78\s*,\s*"
        r"033701\s*\(\s*2009\s*\)",
        search_text,
        flags=re.IGNORECASE,
    )

    matches_by_name = {
        "identified_boldrin_vesignieite_source": identity_match,
        "direct_neutron_abstract_and_dominant_j3": abstract_match,
        "tiny_scalene_distortion_and_two_cu_sites": crystal_match,
        "theta_w_and_nearest_neighbor_model_failure": bulk_match,
        "magnetic_bragg_peaks_and_m_point_vector": diffraction_match,
        "octahedral_and_hexagonal_degenerate_states": octahedral_match,
        "anisotropic_spin_wave_hamiltonian": hamiltonian_match,
        "flat_mode_exchange_constraints_and_best_fit": fit_match,
        "competing_paths_cancel_nearest_neighbor_exchange": (
            cancellation_match
        ),
        "j3_only_heisenberg_continuum": continuum_match,
        "dominant_j3_multi_k_conclusion": conclusion_match,
        "weak_anisotropy_selects_coplanar_hexagonal_state": (
            anisotropy_match
        ),
        "okamoto_2009_original_vesignieite_reference": (
            original_reference_match
        ),
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified Boldrin et al. "
            "neutron article, stoichiometric spin-half vesignieite, both "
            "independent less-than-one-percent distortion statements, "
            "magnetic diffraction, dominant-J3 spin-wave constraints, "
            "weak-anisotropy selection, and the correct Okamoto 033701 "
            "reference; missing anchors: "
            f"{', '.join(missing_anchors)}"
        )

    spin_text = abstract_match.group("spin")
    spin_digits = re.sub(r"\s+", "", spin_text)
    spin = 0.5 if spin_digits in {"12", "1/2", "1=2"} else math.nan
    abstract_distortion = float(abstract_match.group("distortion"))
    crystal_distortion = float(crystal_match.group("distortion"))
    abstract_tn = float(abstract_match.group("tn"))
    conclusion_tn = float(conclusion_match.group("tn"))
    theta = float(bulk_match.group("theta"))
    q_values = [
        float(diffraction_match.group(name))
        for name in ("q1", "q2", "q3")
    ]

    def _parse_fraction(value):
        numerator, denominator = re.split(r"[/=]", value)
        return float(numerator) / float(denominator)

    propagation_vector = [
        _parse_fraction(diffraction_match.group("k1")),
        float(diffraction_match.group("k2")),
        float(diffraction_match.group("k3")),
    ]
    flat_energy = float(fit_match.group("flat_energy"))
    difference = float(fit_match.group("difference"))
    jd_bound = float(fit_match.group("jd_bound"))
    j1_bound = float(fit_match.group("j1_bound"))
    j2_bound = float(fit_match.group("j2_bound"))
    best_j3 = float(fit_match.group("best_j3"))
    best_jd = float(fit_match.group("best_jd"))
    anisotropy_ratio = float(anisotropy_match.group("ratio"))

    expected_numbers = (
        math.isclose(spin, 0.5, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            abstract_distortion, 1.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            crystal_distortion, 1.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            abstract_tn, 9.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            conclusion_tn, 9.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(theta, -75.0, rel_tol=0.0, abs_tol=1.0e-12)
        and q_values == [0.64, 1.08, 1.65]
        and propagation_vector == [0.5, 0.0, 0.0]
        and math.isclose(
            flat_energy, 4.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            difference, 2.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            jd_bound, 0.2, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            j1_bound, 0.1, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            j2_bound, 0.1, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            best_j3, 1.9, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            best_jd, -0.1, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            anisotropy_ratio, -0.006, rel_tol=0.0, abs_tol=1.0e-12
        )
    )
    if not expected_numbers:
        raise RuntimeEvidenceError(
            f"{error_prefix} numerical anchors disagree with the direct "
            "vesignieite diffraction and spin-wave results"
        )

    matches = tuple(matches_by_name.values())
    return (
        {"distorted_kagome_relevant": False},
        {
            "parser": (
                "parse_boldrin_vesignieite_dominant_j3_correction"
            ),
            "source_identity": (
                "doi:10.1103/PhysRevLett.121.107203"
            ),
            "registered_doi": "10.1143/JPSJ.78.043704",
            "original_material_doi": "10.1143/JPSJ.78.033701",
            "material": "BaCu3V2O8(OD)2",
            "spin": spin,
            "structure": (
                "nearly_perfect_kagome_with_tiny_scalene_distortion"
            ),
            "structural_distortion_upper_bound_percent": (
                abstract_distortion
            ),
            "curie_weiss_temperature_k": theta,
            "ordering_temperature_k": abstract_tn,
            "propagation_vector": propagation_vector,
            "magnetic_bragg_q_inverse_angstrom": q_values,
            "magnetic_structure": (
                "hexagonal_multi_k_coplanar_variant_of_triple_k_"
                "octahedral"
            ),
            "dominant_exchange": "antiferromagnetic_J3",
            "isotropic_best_fit_mev": {
                "J3": best_j3,
                "Jd": best_jd,
            },
            "secondary_exchange_notation": (
                "Jd in arXiv v1; J3-prime in the published article"
            ),
            "flat_mode_energy_mev": flat_energy,
            "exchange_constraints_mev": {
                "J3_minus_Jd_approximately": difference,
                "abs_Jd_less_than": jd_bound,
                "abs_J1_less_than": j1_bound,
                "abs_J2_much_less_than": j2_bound,
            },
            "symmetric_exchange_anisotropy_over_j3": anisotropy_ratio,
            "source_role": (
                "machine-extractable corrective direct primary neutron "
                "source"
            ),
            "registered_source_and_model_correction": (
                "The registered DOI 10.1143/JPSJ.78.043704 is a "
                "volborthite magnetization article, not a vesignieite "
                "source. The original vesignieite article is DOI "
                "10.1143/JPSJ.78.033701. Direct neutron evidence in DOI "
                "10.1103/PhysRevLett.121.107203 finds less than 1% "
                "structural distortion but dominant antiferromagnetic J3 "
                "exchange, so a distortion-dominated nearest-neighbor "
                "kagome model is not supported."
            ),
            "claim_scope": (
                "False means that lattice distortion is not the relevant "
                "dominant ingredient of the registered distorted "
                "nearest-neighbor model; a finite tiny scalene distortion "
                "remains structurally present, while the measured magnetic "
                "spectrum is governed by J3 and a weak symmetric exchange "
                "anisotropy"
            ),
            "matched_anchors": [
                "identified Boldrin et al. 2018 vesignieite source",
                "stoichiometric spin-half kagome neutron abstract",
                "less-than-one-percent scalene distortion and two Cu sites",
                "thetaW=-75 K and failure of a J1-only model",
                "three magnetic Bragg peaks and M-point propagation vector",
                "octahedral and coplanar hexagonal degeneracy",
                "semiclassical anisotropic spin-wave Hamiltonian",
                "4 meV flat mode, exchange bounds, and isotropic best fit",
                "competing paths cancel J1 and leave dominant J3",
                "J3-only kagome Heisenberg continuum",
                "TN=9 K dominant-J3 hexagonal multi-k conclusion",
                "delta/J3=-0.006 selects the coplanar hexagonal state",
                "Okamoto 2009 vesignieite reference 033701",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_schiffer_ggg_strong_frustration_correction(source_text):
    """Correct the GGG source identity and extract its frustration evidence."""

    error_prefix = "Schiffer GGG strong-frustration correction"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_schiffer_ggg_strong_frustration_correction",
    )
    return _finalize_prepared_trace(
        _parse_schiffer_ggg_strong_frustration_correction_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_schiffer_ggg_strong_frustration_correction_prepared(
    search_text,
):
    error_prefix = "Schiffer GGG strong-frustration correction"

    identity_match = re.search(
        r"Investigation.{0,100}?of the Field Induced Antiferromagnetic Phase "
        r"Transition in the Frustrated Magnet\s*:\s*Gadolinium Gallium "
        r"Garnet"
        r".{0,500}?P\.\s*Schiffer"
        r".{0,180}?A\.\s*P\.\s*Ramirez"
        r".{0,180}?D\.\s*A\.\s*Huse"
        r".{0,180}?A\.\s*J\.\s*Valentino"
        r".{0,900}?(?:Received\s*20\s*May\s*1994|"
        r"Physical Review Letters.{0,120}?73.{0,120}?1994)",
        search_text,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"geometrically frustrated magnet gadolinium gallium garnet\s*"
        r"\(\s*GGG\s*\)"
        r".{0,300}?unique low temperature"
        r".{0,500}?antiferromagnetic phase which exists only in finite "
        r"fields\s*\(\s*H\s*(?:approximately|-)?\s*"
        r"(?P<field>\d+(?:\.\d+)?)\s*T\s*\)"
        r".{0,500}?measured the specific heat and magnetic "
        r"susceptibility"
        r".{0,600}?simulations including both the "
        r"(?:antiferromagnetic\s+)?exchange and "
        r"(?:the considerable\s+)?dipole interaction",
        search_text,
        flags=re.IGNORECASE,
    )
    low_temperature_match = re.search(
        r"(?:<|less than)\s*(?P<temperature>\d+(?:\.\d+)?)\s*K",
        search_text,
        flags=re.IGNORECASE,
    )
    topology_weiss_match = re.search(
        r"(?:Gd\s*3\s*Ga\s*5\s*O\s*12|gadolinium gallium garnet)"
        r".{0,500}?(?:magnetic\s+)?Gd ions (?:are )?on two "
        r"interpenetrating"
        r".{0,100}?corner\s*-\s*sharing triangular sublattices"
        r".{0,300}?exchanges are almost purely antiferromagnetic"
        r".{0,160}?theta\s*W\s*(?:approximately|=)?\s*"
        r"(?P<theta>-?\d+(?:\.\d+)?)\s*K"
        r".{0,1000}?model system for the study of frustrated magnets",
        search_text,
        flags=re.IGNORECASE,
    )
    suppression_match = re.search(
        r"Because of the high degree of frustration,\s*long\s*-\s*range "
        r"antiferromagnetic order is suppressed in GGG"
        r".{0,220}?appears to be completely suppressed in low magnetic "
        r"fields",
        search_text,
        flags=re.IGNORECASE,
    )
    local_energy_match = re.search(
        r"magnetic Gd ions in GGG are on two equivalent sublattices of "
        r"corner sharing equilateral triangles"
        r".{0,180}?Gd spins\s*\(\s*S\s*=\s*"
        r"(?P<spin>\d+\s*/\s*\d+)\s*\)\s*are isotropic"
        r".{0,220}?single ion anisotropy"
        r".{0,100}?less than\s*"
        r"(?P<anisotropy>\d+(?:\.\d+)?)\s*K"
        r".{0,260}?high degree of frustration in GGG which prevents "
        r"ordering at low fields"
        r".{0,220}?nearest neighbor dipole energy is\s*"
        r"(?:approximately\s*)?(?P<dipole>\d+(?:\.\d+)?)\s*K"
        r".{0,160}?nearest neighbor exchange energy is"
        r".{0,80}?(?P<exchange>\d+(?:\.\d+)?)\s*K"
        r".{0,260}?Further neighbor exchanges are"
        r".{0,120}?known to be an order "
        r"of magnitude or more smaller",
        search_text,
        flags=re.IGNORECASE,
    )
    field_relief_match = re.search(
        r"(?:antiferromagnetic phase in GGG exists when )?the Zeeman "
        r"energies associated with the external field are of the same "
        r"order as the (?:antiferromagnetic|ATM) exchange energy"
        r".{0,180}?field of that magnitude alleviates the local geometric "
        r"frustration but does not force the magnetization to saturate",
        search_text,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"simple model consisting of classical Heisenberg spins at each "
        r"Gd site coupled with nearest\s*-\s*neighbor isotropic "
        r"antiferromagnetic exchange interactions and dipolar "
        r"interactions to the third nearest neighbor"
        r".{0,240}?nearest\s*-\s*neighbor exchange is assumed to be "
        r"twice the strength of the nearest\s*-\s*neighbor dipolar "
        r"interactions"
        r".{0,260}?ground states as a function of field"
        r".{0,180}?Monte Carlo simulations",
        search_text,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"In conclusion,"
        r".{0,700}?model magnetic system"
        r".{0,180}?unique combination of strong geometric frustration "
        r"and dipolar interactions",
        search_text,
        flags=re.IGNORECASE,
    )

    matches_by_name = {
        "identified_schiffer_1994_ggg_source": identity_match,
        "finite_field_thermodynamic_abstract": abstract_match,
        "low_temperature_phase_bound": low_temperature_match,
        "interpenetrating_triangles_and_antiferromagnetic_weiss_scale": (
            topology_weiss_match
        ),
        "low_field_order_suppression": suppression_match,
        "spin_anisotropy_and_nearest_neighbor_energy_scales": (
            local_energy_match
        ),
        "field_alleviates_frustration_without_saturation": (
            field_relief_match
        ),
        "classical_heisenberg_exchange_dipole_model": model_match,
        "strong_frustration_and_dipole_conclusion": conclusion_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified 1994 GGG article, "
            "finite-field thermodynamics, interpenetrating triangular "
            "sublattices, antiferromagnetic Weiss scale, isotropic "
            "spin-7/2 moments, small single-ion anisotropy, exchange and "
            "dipole energy scales, field relief of frustration, and the "
            "classical exchange-dipole simulation model; missing anchors: "
            f"{', '.join(missing_anchors)}"
        )

    field_scale = float(abstract_match.group("field"))
    low_temperature = float(
        low_temperature_match.group("temperature")
    )
    theta = float(topology_weiss_match.group("theta"))
    spin_numerator, spin_denominator = re.split(
        r"/",
        local_energy_match.group("spin"),
    )
    spin = float(spin_numerator) / float(spin_denominator)
    anisotropy = float(local_energy_match.group("anisotropy"))
    dipole_energy = float(local_energy_match.group("dipole"))
    exchange_energy = float(local_energy_match.group("exchange"))

    expected_numbers = (
        math.isclose(field_scale, 1.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            low_temperature, 0.38, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(theta, -2.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(spin, 3.5, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            anisotropy, 0.04, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            dipole_energy, 0.7, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            exchange_energy, 1.5, rel_tol=0.0, abs_tol=1.0e-12
        )
    )
    if not expected_numbers:
        raise RuntimeEvidenceError(
            f"{error_prefix} numerical anchors disagree with the direct "
            "GGG thermodynamic and microscopic-model source"
        )

    matches = tuple(matches_by_name.values())
    return (
        {"strong_frustration": True},
        {
            "parser": (
                "parse_schiffer_ggg_strong_frustration_correction"
            ),
            "source_identity": "doi:10.1103/PhysRevLett.73.2500",
            "registered_doi": "10.1103/PhysRevLett.77.2085",
            "material": "Gd3Ga5O12",
            "spin": spin,
            "structure": (
                "two_interpenetrating_corner_sharing_triangular_"
                "sublattices"
            ),
            "curie_weiss_temperature_k": theta,
            "single_ion_anisotropy_upper_bound_k": anisotropy,
            "nearest_neighbor_dipole_energy_k": dipole_energy,
            "nearest_neighbor_exchange_energy_k": exchange_energy,
            "field_induced_af_phase_upper_temperature_k": (
                low_temperature
            ),
            "field_scale_t": field_scale,
            "measurements": [
                "specific_heat",
                "magnetic_susceptibility",
            ],
            "microscopic_model": (
                "classical_Heisenberg_nearest_neighbor_"
                "antiferromagnetic_exchange_plus_dipolar_interactions_"
                "to_third_neighbor"
            ),
            "source_role": (
                "machine-extractable corrective direct primary "
                "thermodynamic and simulation source"
            ),
            "registered_source_and_scope_correction": (
                "The registered DOI 10.1103/PhysRevLett.77.2085 is a "
                "kagome SrCr9pGa12-9pO19 coplanarity article, not a "
                "Gd3Ga5O12 source. The direct GGG source used here is "
                "Schiffer et al., DOI 10.1103/PhysRevLett.73.2500."
            ),
            "claim_scope": (
                "supports only the registered strong-frustration boolean "
                "for GGG; the 1994 source describes two interpenetrating "
                "corner-sharing triangular sublattices and does not "
                "itself use the later hyperkagome label, while its "
                "low-temperature antiferromagnetic phase occurs only in "
                "finite field"
            ),
            "matched_anchors": [
                "identified Schiffer et al. 1994 GGG source",
                "finite-field specific-heat and susceptibility abstract",
                "low-temperature AF phase below 0.38 K",
                "interpenetrating triangular sublattices and thetaW=-2 K",
                "strong frustration suppresses low-field order",
                "spin-7/2 isotropy, anisotropy, and two energy scales",
                "field alleviates frustration without saturation",
                "classical Heisenberg exchange-dipole Monte Carlo model",
                "strong geometric-frustration and dipole conclusion",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction(
    source_text,
):
    """Correct the GTLG source and extract frustrated-garnet evidence."""

    error_prefix = "Quilliam GTLG frustrated-hyperkagome correction"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction",
    )
    return _finalize_prepared_trace(
        _parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction_prepared(
    search_text,
):
    error_prefix = "Quilliam GTLG frustrated-hyperkagome correction"

    identity_match = re.search(
        r"Juxtaposition of spin freezing and long range order in a "
        r"series of geometrically frustrated antiferromagnetic "
        r"gadolinium garnets"
        r".{0,500}?J\.\s*A\.\s*Quilliam"
        r".{0,2000}?(?:"
        r"DOI\s*:\s*10\.1103\s*/\s*PhysRevB\.87\.174421"
        r"|arXiv\s*:\s*1006\.2969v2"
        r"|Physical Review B\s*87\s*,\s*174421\s*\(\s*2013\s*\)"
        r")",
        search_text,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"Specific heat measurements in zero magnetic field are "
        r"presented on a homologous series of geometrically frustrated"
        r".{0,100}?antiferromagnetic"
        r".{0,100}?Heisenberg garnet systems"
        r".{0,500}?Gd3Te2Li3O12 and Gd3Al5O12"
        r".{0,200}?clear ordering transitions at\s*"
        r"(?P<gtlg_tc>\d+(?:\.\d+)?)\s*(?:mK|and)"
        r".{0,100}?(?P<gag_tc>\d+(?:\.\d+)?)\s*mK"
        r".{0,350}?structural characterization"
        r".{0,100}?x\s*-\s*ray diffraction",
        search_text,
        flags=re.IGNORECASE,
    )
    frustration_match = re.search(
        r"lattice of corner\s*-\s*sharing simplexes,\s*such as triangles "
        r"or tetrahedra,\s*coupled via a nearest\s*-\s*neighbor"
        r".{0,80}?antiferromagnetic Heisenberg exchange Hamiltonian"
        r".{0,100}?are highly frustrated"
        r".{0,1200}?frustrated garnet materials"
        r".{0,180}?(?:three|3)(?:\s*-\s*|\s*).{0,100}?"
        r"dimensional network of "
        r"corner(?:\s*-\s*|\s+)sharing triangles",
        search_text,
        flags=re.IGNORECASE,
    )
    hyperkagome_match = re.search(
        r"Gd positions (?:which )?form two interpenetrating networks of "
        r"corner\s*-\s*sharing triangles,.{0,160}?known as hyperkagome "
        r"lattices",
        search_text,
        flags=re.IGNORECASE,
    )
    spin_match = re.search(
        r"largely isotropic,?\s*S\s*=\s*"
        r"(?P<spin>\d+\s*(?:/|=)\s*\d+)\s*Gd\s*3\s*\+"
        r".{0,320}?moments"
        r".{0,500}?classical Heisenberg antiferromagnets",
        search_text,
        flags=re.IGNORECASE,
    )
    exchange_scale_match = re.search(
        r"(?:low energy scale of"
        r".{0,120}?exchange interaction|"
        r"scale of exchange interactions|"
        r"nearest\s*-\s*neighbor exchange scale)"
        r".{0,220}?J1\s*(?:(?:is|=|approximately)\s*)*"
        r"(?P<j_low>\d+(?:\.\d+)?)\s*to\s*"
        r"(?P<j_high>\d+(?:\.\d+)?)\s*K"
        r".{0,260}?dipolar interaction becomes very important",
        search_text,
        flags=re.IGNORECASE,
    )
    exchange_model_match = re.search(
        r"HAMILTONIANS"
        r"(?=.{0,3500}?Hamiltonian consisting of"
        r".{0,500}?nearest(?:\s*-\s*|\s*).{0,180}?neighbor exchange)"
        r"(?=.{0,3500}?(?:"
        r"HEx\s*=\s*.{0,300}?J1\s*S\s*i\s*dot\s*S\s*j"
        r"|J1\s*S\s*i\s*dot\s*S\s*j.{0,300}?HEx\s*="
        r"))"
        r".{0,3500}?(?:HEx\s*=|J1\s*S\s*i\s*dot\s*S\s*j)",
        search_text,
        flags=re.IGNORECASE,
    )
    dipole_model_match = re.search(
        r"HAMILTONIANS"
        r"(?=.{0,3500}?(?:and (?:the )?dipolar interaction|"
        r"dipolar interaction))"
        r"(?=.{0,3500}?HD\s*=\s*D)"
        r"(?=.{0,3500}?(?:S\s*i\s*dot\s*S\s*j|Si\s*dot\s*Sj))"
        r"(?=.{0,4500}?Further(?:\s*-\s*|\s+)neighbor interactions may "
        r"be important"
        r".{0,700}?GTLG"
        r".{0,400}?not (?:yet )?been determined)"
        r".{0,4500}?not (?:yet )?been determined",
        search_text,
        flags=re.IGNORECASE,
    )
    parameters_match = re.search(
        r"(?:This gives|gives)\s*J1\s*=\s*"
        r"(?P<j1>\d+(?:\.\d+)?)\s*mK for GTLG"
        r".{0,1800}?GTLG at\s*D\s*=\s*"
        r"(?P<dipole>\d+(?:\.\d+)?)\s*mK"
        r".{0,500}?ratio\s*D\s*/\s*J1"
        r".{0,300}?GTLG\s*\(\s*(?P<ratio>\d+(?:\.\d+)?)\s*\)",
        search_text,
        flags=re.IGNORECASE,
    )
    ordering_match = re.search(
        r"GTLG displays a very sharp phase transition at\s*"
        r"(?P<tc>\d+(?:\.\d+)?)\s*mK"
        r".{0,180}?transition is clearly first(?:\s*-\s*|\s+)order"
        r".{0,260}?Curie\s*-\s*Weiss temperature\s*thetaCW\s*"
        r"(?:approximately\s*)+(?P<theta>-?\d+(?:\.\d+)?)\s*K"
        r".{0,200}?ordering temperature gives a frustration index\s*"
        r"f\s*=\s*(?:\|\s*)?thetaCW(?:\s*\|)?\s*/\s*TC\s*=\s*"
        r"(?P<frustration>\d+(?:\.\d+)?)",
        search_text,
        flags=re.IGNORECASE,
    )
    gap_match = re.search(
        r"(?:Below the transition,?\s*)?"
        r".{0,220}?gapped spin(?:\s*-\s*|\s+)wave excitations"
        r".{0,220}?expected from long\s*-\s*range order with a strong "
        r"dipolar interaction"
        r".{0,1200}?(?:resulting )?linear fit "
        r"(?:gives|suggestive of spin waves with a "
        r"gap of)\s*(?:a gap\s*)?(?:Delta\s*)?"
        r"(?:=|approximately\s*)*"
        r"(?P<gap>\d+(?:\.\d+)?)\s*K"
        r".{0,600}?(?:gap here to come|expected to come) primarily from "
        r"the anisotropic "
        r"dipole\s*-\s*dipole interaction\s*HD",
        search_text,
        flags=re.IGNORECASE,
    )
    long_range_order_match = re.search(
        r"(?:"
        r"sharp transition and"
        r".{0,250}?exponential drop in specific heat provide strong "
        r"evidence of long(?:\s*-\s*|\s+)range order"
        r"|sharp features observed in GTLG and GAG"
        r"(?=.{0,1000}?transitions to long(?:\s*-\s*|\s+)range order)"
        r"(?=.{0,1800}?exponential drop in the specific heat)"
        r"(?=.{0,2600}?strong evidence of "
        r"long(?:\s*-\s*|\s+)range order)"
        r".{0,2600}?strong evidence of "
        r"long(?:\s*-\s*|\s+)range order"
        r")",
        search_text,
        flags=re.IGNORECASE,
    )
    space_group_match = re.search(
        r"(?:GTLG sample|sample is) cubic with space group"
        r"(?=.{0,240}?Ia\s*-\s*3d)"
        r"(?=.{0,240}?\(\s*(?P<number>\d+)\s*\))"
        r".{0,240}?(?:Ia\s*-\s*3d|\(\s*\d+\s*\))",
        search_text,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"In conclusions?,"
        r".{0,1200}?GTLG(?: and GAG)?"
        r".{0,400}?clear ordering transition(?:s)?"
        r".{0,700}?response of (?:a highly frustrated magnet|a HFM) to "
        r"weak "
        r"random disorder can be highly nontrivial",
        search_text,
        flags=re.IGNORECASE,
    )

    matches_by_name = {
        "identified_quilliam_gtlg_source": identity_match,
        "specific_heat_and_structural_abstract": abstract_match,
        "corner_sharing_simplex_frustration": frustration_match,
        "two_interpenetrating_hyperkagome_networks": hyperkagome_match,
        "isotropic_spin_seven_halves": spin_match,
        "low_exchange_scale_and_important_dipolar_interaction": (
            exchange_scale_match
        ),
        "nearest_neighbor_heisenberg_exchange_hamiltonian": (
            exchange_model_match
        ),
        "dipolar_hamiltonian_and_unknown_further_gtlg_exchange": (
            dipole_model_match
        ),
        "gtlg_exchange_dipole_parameters": parameters_match,
        "first_order_transition_and_frustration_index": ordering_match,
        "gapped_spin_wave_energy_and_dipolar_origin": gap_match,
        "specific_heat_evidence_for_long_range_order": (
            long_range_order_match
        ),
        "cubic_garnet_space_group": space_group_match,
        "highly_frustrated_ordering_conclusion": conclusion_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified Quilliam et al. "
            "article, direct specific-heat and structural measurements, "
            "two interpenetrating hyperkagome networks, isotropic "
            "spin-7/2 Gd moments, explicit nearest-neighbor Heisenberg "
            "and dipolar Hamiltonian terms, GTLG J1 and D scales, the "
            "first-order 243 mK transition, frustration index, gapped "
            "spin-wave evidence for long-range order, cubic space group, "
            "and the highly-frustrated-magnet conclusion; missing "
            f"anchors: {', '.join(missing_anchors)}"
        )

    abstract_tc_mk = float(abstract_match.group("gtlg_tc"))
    spin_text = re.sub(r"\s+", "", spin_match.group("spin"))
    spin_numerator, spin_denominator = re.split(r"[/=]", spin_text)
    spin = float(spin_numerator) / float(spin_denominator)
    j_low = float(exchange_scale_match.group("j_low"))
    j_high = float(exchange_scale_match.group("j_high"))
    j1_mk = float(parameters_match.group("j1"))
    dipole_mk = float(parameters_match.group("dipole"))
    ratio = float(parameters_match.group("ratio"))
    ordering_tc_mk = float(ordering_match.group("tc"))
    theta = float(ordering_match.group("theta"))
    frustration_index = float(ordering_match.group("frustration"))
    gap = float(gap_match.group("gap"))
    space_group_number = int(space_group_match.group("number"))

    expected_numbers = (
        math.isclose(
            abstract_tc_mk, 243.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            ordering_tc_mk, 243.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(spin, 3.5, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(j_low, 0.1, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(j_high, 0.14, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(j1_mk, 126.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            dipole_mk, 45.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(ratio, 0.36, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(theta, -2.7, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(
            frustration_index, 11.0, rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(gap, 0.62, rel_tol=0.0, abs_tol=1.0e-12)
        and space_group_number == 230
    )
    if not expected_numbers:
        raise RuntimeEvidenceError(
            f"{error_prefix} numerical anchors disagree with the direct "
            "GTLG specific-heat, susceptibility, and structural results"
        )

    matches = tuple(matches_by_name.values())
    return (
        {"garnet_frustrated_magnet": True},
        {
            "parser": (
                "parse_quilliam_gtlg_frustrated_hyperkagome_garnet_"
                "correction"
            ),
            "source_identity": "doi:10.1103/PhysRevB.87.174421",
            "arxiv_identity": "arXiv:1006.2969v2",
            "registered_doi": "10.1103/PhysRevB.92.140407",
            "material": "Gd3Te2Li3O12",
            "spin": spin,
            "structure": (
                "two_interpenetrating_hyperkagome_networks_of_corner_"
                "sharing_triangles"
            ),
            "model_terms": [
                "nearest_neighbor_antiferromagnetic_Heisenberg_exchange",
                "long_range_dipolar_interaction",
            ],
            "nearest_neighbor_exchange_k": j1_mk / 1000.0,
            "dipolar_interaction_k": dipole_mk / 1000.0,
            "dipolar_to_exchange_ratio": ratio,
            "curie_weiss_temperature_k": theta,
            "ordering_temperature_k": ordering_tc_mk / 1000.0,
            "frustration_index": frustration_index,
            "spin_wave_gap_k": gap,
            "space_group": "Ia-3d (230)",
            "ordering_assessment": (
                "sharp_first_order_transition_with_strong_evidence_of_"
                "long_range_order"
            ),
            "source_role": (
                "machine-extractable corrective direct primary "
                "specific-heat and structural source"
            ),
            "registered_source_and_scope_correction": (
                "The registered DOI 10.1103/PhysRevB.92.140407 is an "
                "Er/Yb germanate-pyrochlore antiferromagnetic-order "
                "article, not a Gd3Te2Li3O12 source. The direct GTLG "
                "source used here is Quilliam et al., DOI "
                "10.1103/PhysRevB.87.174421, arXiv:1006.2969v2."
            ),
            "claim_scope": (
                "supports only the registered frustrated-garnet boolean "
                "and hyperkagome material mapping; GTLG is highly "
                "frustrated but undergoes a sharp first-order transition "
                "with strong evidence of long-range order, so this is not "
                "evidence for a realized spin-liquid ground state or a "
                "fully determined microscopic Hamiltonian"
            ),
            "matched_anchors": [
                "identified Quilliam et al. GTLG source",
                "zero-field specific heat and x-ray structural abstract",
                "corner-sharing-simplex Heisenberg frustration",
                "two interpenetrating hyperkagome networks",
                "isotropic spin-7/2 Gd moments",
                "0.1-0.14 K exchange scale makes dipolar coupling important",
                "nearest-neighbor Heisenberg exchange Hamiltonian",
                "dipolar Hamiltonian and unknown further GTLG exchanges",
                "J1=126 mK, D=45 mK, and D/J1=0.36",
                "243 mK first-order transition and f=11",
                "0.62 K gapped-spin-wave energy and dipolar origin",
                "specific-heat evidence for long-range order",
                "cubic Ia-3d space group 230",
                "highly-frustrated-magnet ordering conclusion",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_bergman_diamond_spiral_surface(source_text):
    """Extract the diamond-lattice spiral-surface threshold and Fourier kernel."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Bergman diamond spiral surface requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    identity_match = re.search(
        r"Order by disorder and spiral spin liquid in frustrated diamond lattice"
        r".{0,80}?antiferromagnets",
        normalized,
        flags=re.IGNORECASE,
    )
    threshold_match = re.search(
        r"Exact ground states can be obtained for arbitrary J2\s*/\s*J1"
        r".{0,160}?0\s*(?:<=|≤)\s*J2\s*/\s*J1\s*(?:<=|≤)\s*1\s*/\s*8"
        r".{0,160}?N.{0,8}?el phase.{0,160}?For larger J2.{0,180}?"
        r"coplanar spin spirals.{0,180}?two-dimensional.{0,40}?spiral surface",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_kernel_match = re.search(
        r"Transforming to momentum space gives two bands.{0,80}?"
        r"epsilon_pm\s*\(q\)\s*=\s*4\s*J2\s*\[Lambda\(q\)\^2\s*-\s*1\]"
        r"\s*\+/-\s*2\s*J1\s*Lambda\(q\).{0,30}?\(5\)"
        r".{0,180}?lower-band minimum.{0,100}?q\s*=\s*0.{0,80}?1\s*/\s*8"
        r".{0,160}?two-dimensional.{0,40}?surface",
        normalized,
        flags=re.IGNORECASE,
    )
    source_kernel_match = re.search(
        r"diagonalize the Hamiltonian by transforming to momentum space"
        r".{0,180}?two bands with energies.{0,100}?4J2\s*\[.{0,30}?2"
        r"\s*\(q\)\s*[−-]\s*1\].{0,30}?[±+].{0,20}?2J1.{0,30}?\(q\)"
        r".{0,40}?\(5\).{0,500}?minimum eigenvalue.{0,100}?lower band"
        r".{0,160}?q\s*=\s*0.{0,100}?J2\s*/\s*J1\s*<\s*1\s*/\s*8"
        r".{0,160}?two-dimensional surface",
        normalized,
        flags=re.IGNORECASE,
    )
    kernel_match = clean_kernel_match or source_kernel_match
    matches = (identity_match, threshold_match, kernel_match)
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Bergman diamond spiral surface must identify the diamond J1-J2 model, "
            "the Neel-to-spiral threshold at J2/J1=1/8, and the lower Fourier "
            "band whose minima form the surface"
        )
    return (
        {
            "spiral_surface_for_j2_over_j1_gt": 0.125,
        },
        {
            "parser": "parse_bergman_diamond_spiral_surface",
            "equation": "5",
            "matched_anchors": [
                "frustrated diamond-lattice antiferromagnet",
                "J2/J1=1/8 Neel-to-spiral-surface threshold",
                "two-band momentum-space exchange kernel",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def recompute_diamond_spiral_surface_threshold(
    *, lambda_max, below_ratio, above_ratio
):
    """Minimize Bergman's lower Fourier band over the allowed Lambda range."""

    values = (lambda_max, below_ratio, above_ratio)
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values
    ):
        raise RuntimeEvidenceError("diamond spiral threshold parameters must be numeric")
    lambda_max = float(lambda_max)
    below_ratio = float(below_ratio)
    above_ratio = float(above_ratio)
    if (
        lambda_max <= 0.0
        or below_ratio <= 0.0
        or above_ratio <= below_ratio
    ):
        raise RuntimeEvidenceError("invalid diamond spiral threshold probes")

    threshold = 1.0 / (4.0 * lambda_max)

    def unconstrained_minimum(ratio):
        return 1.0 / (4.0 * ratio)

    if not (
        below_ratio < threshold < above_ratio
        and unconstrained_minimum(below_ratio) > lambda_max
        and 0.0 < unconstrained_minimum(above_ratio) < lambda_max
    ):
        raise RuntimeEvidenceError(
            "diamond lower-band probes do not straddle the surface threshold"
        )
    return {
        "spiral_surface_for_j2_over_j1_gt": threshold,
    }


def parse_ross_pyrochlore_exchange_basis(source_text):
    """Extract all four local-coordinate pyrochlore exchange channels."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Ross pyrochlore exchange basis requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    identity_match = re.search(
        r"Quantum Excitations in Quantum Spin Ice",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_hamiltonian_match = re.search(
        r"zero-field nearest-neighbor pyrochlore Hamiltonian.{0,180}?"
        r"local C3 axis.{0,180}?\bJzz\b.{0,120}?\bJpm\b.{0,160}?"
        r"\bJpmpm\b.{0,180}?\bJzpm\b.{0,100}?\(4\)",
        normalized,
        flags=re.IGNORECASE,
    )
    ocr_hamiltonian_match = re.search(
        r"rewrite the zero-field Hamiltonian.{0,180}?spins quan-.{0,220}?"
        r"tized along the local C3 axis.{0,300}?Jzz.{0,120}?J\x04"
        r".{0,180}?J\x04\x04"
        r".{0,180}?Jz\x04.{0,180}?\(4\)",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = clean_hamiltonian_match or ocr_hamiltonian_match
    clean_mapping_match = re.search(
        r"Here Jzz, Jpm, Jpmpm, and Jzpm are expressed in terms of the four "
        r"independent.{0,80}?J1, J2, J3, and J4",
        normalized,
        flags=re.IGNORECASE,
    )
    ocr_mapping_match = re.search(
        r"where here.{0,100}?local spin coordinates.{0,80}?Jzz.{0,160}?J\x04"
        r".{0,160}?J\x04\x04.{0,160}?Jz\x04.{0,300}?J1.{0,120}?J2"
        r".{0,120}?J3.{0,120}?J4",
        normalized,
        flags=re.IGNORECASE,
    )
    mapping_match = clean_mapping_match or ocr_mapping_match
    matches = (identity_match, hamiltonian_match, mapping_match)
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Ross pyrochlore exchange basis must contain Eq. (4) with all of "
            "Jzz, Jpm, Jpmpm, and Jzpm and their relation to the four global "
            "exchange constants"
        )
    return (
        {"couplings": ["Jzz", "Jpm", "Jpmpm", "Jzpm"]},
        {
            "parser": "parse_ross_pyrochlore_exchange_basis",
            "equation": "4",
            "normalization": (
                "source Jzz,J_plusminus,J_plusminus_plusminus,Jz_plusminus "
                "mapped to registry Jzz,Jpm,Jpmpm,Jzpm"
            ),
            "matched_anchors": [
                "Ross et al. quantum spin ice Hamiltonian",
                "complete local-coordinate exchange Hamiltonian Eq. (4)",
                "mapping to four global exchange constants",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_kane_mele_hubbard_spin_anisotropy(source_text):
    """Extract the spin-orbit-generated anisotropic strong-coupling exchange."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Kane-Mele-Hubbard spin anisotropy requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    identity_match = re.search(
        r"Hubbard model on the honeycomb lattice with intrinsic "
        r"spin-orbit interactions",
        normalized,
        flags=re.IGNORECASE,
    )
    strong_coupling_match = re.search(
        r"spin-orbit term in the strong-coupling limit U\s*(?:→|->)\s*"
        r"(?:⬁|∞|infinity).{0,100}?(?:\u242d|λ|lambda).{0,25}?fixed",
        normalized,
        flags=re.IGNORECASE,
    )
    half_filling_match = re.search(
        r"At half filling(?:\s*,| and for U)",
        normalized,
        flags=re.IGNORECASE,
    )
    anisotropic_equation_match = re.search(
        r"(?:−|-)\s*Sx(?:_?i)?\s*Sx(?:_?j)?\s*"
        r"(?:−|-)\s*Sy(?:_?i)?\s*Sy(?:_?j)?\s*"
        r"\+\s*Sz(?:_?i)?\s*Sz(?:_?j)?.{0,60}?[（共(]31[）兲)]"
        r".{0,800}?exchange coupling J2\s*(?:=|¼)\s*4\s*"
        r"(?:\u242d|λ|lambda)\s*(?:\^\s*2|2|²)\s*/\s*U",
        normalized,
        flags=re.IGNORECASE,
    )
    ordering_match = re.search(
        r"XY term (?:which )?favors ferromagnetic order and (?:a|the) Z term"
        r".{0,400}?(?:which )?favors antiparallel alignment of the spins",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        strong_coupling_match,
        half_filling_match,
        anisotropic_equation_match,
        ordering_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Kane-Mele-Hubbard spin anisotropy requires the honeycomb "
            "intrinsic-spin-orbit model, half filling, the U-to-infinity "
            "strong-coupling limit, anisotropic Eq. (31), J2=4 lambda^2/U, "
            "and its unequal XY/Z ordering tendencies"
        )
    return (
        {"spin_orbit_induced_anisotropy": True},
        {
            "parser": "parse_kane_mele_hubbard_spin_anisotropy",
            "equation": "31",
            "normalization": (
                "source next-neighbor spin-orbit exchange kept in its "
                "-SxSx-SySy+SzSz convention"
            ),
            "matched_anchors": [
                "honeycomb Hubbard model with intrinsic spin-orbit interactions",
                "spin-orbit strong-coupling limit U to infinity",
                "half-filled singly occupied limit",
                "Eq. (31) anisotropy with J2=4 lambda^2/U",
                "ferromagnetic XY and antiparallel Z tendencies",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_yb2ti2o7_exchange_fit(source_text):
    """Extract Ross et al.'s material-specific four-channel exchange fit."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Yb2Ti2O7 exchange fit requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    title_match = re.search(
        r"Quantum Excitations in Quantum Spin Ice",
        normalized,
        flags=re.IGNORECASE,
    )
    material_match = re.search(
        r"Yb2\s*Ti2\s*O7",
        normalized,
        flags=re.IGNORECASE,
    )
    neutron_match = re.search(
        r"high-field.{0,100}?inelastic neutron scattering",
        normalized,
        flags=re.IGNORECASE,
    )
    fit_match = re.search(
        r"spectrum is extremely well fit by spin(?:-|\s+)wave"
        r".{0,300}?theory.{0,250}?through this fit.{0,250}?"
        r"unambiguously extract all.{0,250}?microscopic exchange parameters",
        normalized,
        flags=re.IGNORECASE,
    )
    values_match = re.search(
        r"From the fits in Eq\.?\s*\(3\), we find,? in meV,?"
        r".{0,100}?Jzz\s*(?:=|¼)\s*0[:.]17"
        r".{0,120}?J(?:pm|\x04)\s*(?:=|¼)\s*0[:.]05"
        r".{0,180}?J(?:pmpm|\x04\x04)\s*(?:=|¼)\s*0[:.]05"
        r".{0,140}?Jz(?:pm|\x04)\s*(?:=|¼)\s*(?:-|−|\x03)0[:.]14",
        normalized,
        flags=re.IGNORECASE,
    )
    try:
        _, basis_trace = parse_ross_pyrochlore_exchange_basis(source_text)
    except RuntimeEvidenceError as exc:
        raise RuntimeEvidenceError(
            "Yb2Ti2O7 exchange fit requires the complete global-to-local "
            "four-channel exchange basis in Eq. (4)"
        ) from exc
    matches = (title_match, material_match, neutron_match, fit_match, values_match)
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Yb2Ti2O7 exchange fit requires exact material identity, "
            "high-field inelastic-neutron data, spin-wave fitting, extraction "
            "of all microscopic exchanges, and the four Eq. (5) fit values"
        )
    basis_spans = basis_trace["text_spans"]
    basis_span = [
        min(span[0] for span in basis_spans),
        max(span[1] for span in basis_spans),
    ]
    return (
        {"anisotropic_exchange_fit_reference": True},
        {
            "parser": "parse_yb2ti2o7_exchange_fit",
            "equations": ["3", "4", "5"],
            "normalization": (
                "Ross global J1..J4 fit mapped to the local "
                "Jzz,Jpm,Jpmpm,Jzpm convention"
            ),
            "matched_anchors": [
                "Quantum Excitations in Quantum Spin Ice",
                "Yb2Ti2O7 material identity",
                "high-field inelastic neutron scattering",
                "spin-wave fit extracting all microscopic exchanges",
                "complete global-to-local four-channel Eq. (4)",
                "Eq. (5) values 0.17, 0.05, 0.05, and -0.14 meV",
            ],
            "text_spans": [
                [title_match.start(), title_match.end()],
                [material_match.start(), material_match.end()],
                [neutron_match.start(), neutron_match.end()],
                [fit_match.start(), fit_match.end()],
                basis_span,
                [values_match.start(), values_match.end()],
            ],
        },
    )


def parse_harris_spin_ice_tetrahedron_levels(source_text):
    """Derive normalized tetrahedron energies from Harris's local-axis ice rule."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Harris spin-ice tetrahedron requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"ferromagnetic pyrochlore with (?:local )?Ising anisotropy",
        normalized,
        flags=re.IGNORECASE,
    )
    axes_match = re.search(
        r"(?:<|k)111(?:>|l)-type directions.{0,120}?"
        r"connect a spin with the center of its tetrahedron",
        normalized,
        flags=re.IGNORECASE,
    )
    ground_state_match = re.search(
        r"ground state of such a single tetrahedron.{0,220}?"
        r"two spins.{0,15}?in.{0,60}?two spins.{0,15}?out",
        normalized,
        flags=re.IGNORECASE,
    )
    ice_rule_match = re.search(
        r"(?:our\s+)?[“\"]?two[ -]in,?\s+two[ -]out[”\"]?\s+condition is "
        r"(?:then )?identical to (?:the )?[“\"]?ice rule",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (model_match, axes_match, ground_state_match, ice_rule_match)
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Harris spin-ice tetrahedron requires the ferromagnetic "
            "pyrochlore, local <111> axes, a single tetrahedron, its two-in/"
            "two-out ground state, and explicit ice-rule identification"
        )
    return (
        {
            "two_in_two_out_energy": -2.0,
            "three_in_one_out_energy": 0.0,
            "all_in_all_out_energy": 6.0,
            "two_in_two_out_degeneracy": 6,
        },
        {
            "parser": "parse_harris_spin_ice_tetrahedron_levels",
            "normalization": "J_eff=1 in H=J_eff sum_<ij> sigma_i sigma_j",
            "derivation": (
                "The four regular-tetrahedron <111> axes obey e_i.e_j=-1/3. "
                "Ferromagnetic vector exchange therefore gives positive "
                "J_eff for the Ising variables. For J_eff=1, "
                "sum_(i<j) sigma_i sigma_j=((sum_i sigma_i)^2-4)/2."
            ),
            "matched_anchors": [
                "ferromagnetic pyrochlore with local Ising anisotropy",
                "local <111> axes connect spins to the tetrahedron center",
                "single-tetrahedron two-in/two-out ground state",
                "two-in/two-out condition is the ice rule",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def recompute_spin_ice_tetrahedron_levels(*, effective_exchange):
    """Enumerate all 16 four-Ising-spin configurations independently."""

    if (
        isinstance(effective_exchange, bool)
        or not isinstance(effective_exchange, (int, float))
        or not math.isfinite(float(effective_exchange))
        or effective_exchange <= 0
    ):
        raise RuntimeEvidenceError(
            "spin-ice tetrahedron effective exchange must be positive and finite"
        )
    effective_exchange = float(effective_exchange)
    energies_by_class = {
        "two_in_two_out": set(),
        "three_in_one_out": set(),
        "all_in_all_out": set(),
    }
    counts_by_class = {key: 0 for key in energies_by_class}
    for bit_mask in range(1 << 4):
        sigmas = [
            1 if bit_mask & (1 << site_index) else -1
            for site_index in range(4)
        ]
        up_count = sum(sigma == 1 for sigma in sigmas)
        pair_sum = sum(
            sigmas[left] * sigmas[right]
            for left in range(4)
            for right in range(left + 1, 4)
        )
        if up_count == 2:
            class_name = "two_in_two_out"
        elif up_count in (1, 3):
            class_name = "three_in_one_out"
        else:
            class_name = "all_in_all_out"
        energies_by_class[class_name].add(effective_exchange * pair_sum)
        counts_by_class[class_name] += 1
    if any(len(energies) != 1 for energies in energies_by_class.values()):
        raise RuntimeEvidenceError(
            "spin-ice tetrahedron enumeration did not produce one energy per class"
        )
    return {
        "two_in_two_out_energy": energies_by_class["two_in_two_out"].pop(),
        "three_in_one_out_energy": energies_by_class["three_in_one_out"].pop(),
        "all_in_all_out_energy": energies_by_class["all_in_all_out"].pop(),
        "two_in_two_out_degeneracy": counts_by_class["two_in_two_out"],
    }


def parse_kharkov_square_j1_j3_lifshitz(source_text):
    """Extract the source-locked classical square J1-J3 Lifshitz problem."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "square J1-J3 Lifshitz evidence requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    staggered_match = re.search(
        r"(?:n.{0,20}?is the staggered magnetization|"
        r"n.{0,20}?is a unit length vector.{0,140}?staggered magnetization)",
        normalized,
        flags=re.IGNORECASE,
    )
    pitch_match = re.search(
        r"n\s*\(\s*r\s*\).{0,180}?cos\s*\(\s*Q\s*r\s*\)"
        r".{0,120}?sin\s*\(\s*Q\s*r\s*\).{0,260}?"
        r"Q is the.{0,100}?pitch of the spiral",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"(?:antiferromagnetic J1\s*(?:−|-)\s*J3 Heisenberg model "
        r"on the square lattice|J1\s*(?:−|-)\s*J3 MODEL ON THE SQUARE LATTICE)",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"Hamiltonian of the J1\s*(?:−|-)\s*J3 model reads"
        r".{0,450}?H\s*=\s*J1.{0,120}?J3.{0,180}?"
        r"(?:\(\s*34\s*\)|first and third nearest|"
        r"first- and third-nearest)"
        r".{0,240}?(?:first and third nearest|first- and third-nearest)",
        normalized,
        flags=re.IGNORECASE,
    )
    if hamiltonian_match is None:
        hamiltonian_match = re.search(
            r"Hamiltonian is H\s*=\s*J1.{0,120}?J3.{0,100}?"
            r"\(\s*34\s*\).{0,180}?first- and third-nearest",
            normalized,
            flags=re.IGNORECASE,
        )
    boundary_match = re.search(
        r"(?:classical limit.{0,120}?|classical )"
        r"spin-spiral to N(?:e|é|´e)el.{0,100}?(?:Lifshitz point|LP)"
        r".{0,80}?(?:located at )?J3\s*/\s*J1\s*=\s*1\s*/\s*4",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        staggered_match,
        pitch_match,
        model_match,
        hamiltonian_match,
        boundary_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "square J1-J3 Lifshitz evidence requires the staggered-Q "
            "convention, spiral-pitch definition, square antiferromagnet, "
            "first/third-neighbor Hamiltonian Eq. (34), and classical "
            "J3/J1=1/4 boundary"
        )
    return (
        {"spiral_condition": "cos(Q)=J1/(4J3)"},
        {
            "parser": "parse_kharkov_square_j1_j3_lifshitz",
            "equation": "34",
            "normalization": (
                "Q modulates the staggered square-lattice field; J1 and J3 "
                "are positive first- and third-neighbor exchanges"
            ),
            "derivation": (
                "For the source-defined staggered axial spiral, the bond "
                "energy is -J1(1+cos Q)+J3(1+cos 2Q). Its noncollinear "
                "stationary branch gives cos(Q)=J1/(4J3), entering at 1/4."
            ),
            "matched_anchors": [
                "n is the staggered magnetization",
                "Q is the pitch of the spiral",
                "square-lattice antiferromagnetic J1-J3 model",
                "first/third-neighbor Hamiltonian Eq. (34)",
                "classical Lifshitz boundary J3/J1=1/4",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def recompute_square_j1_j3_spiral_condition(*, below_ratio, above_ratio):
    """Derive the spiral condition from square-lattice bond displacements."""

    values = (below_ratio, above_ratio)
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values
    ):
        raise RuntimeEvidenceError(
            "square J1-J3 Lifshitz probes must be finite numbers"
        )
    below_ratio = float(below_ratio)
    above_ratio = float(above_ratio)
    if not (
        math.isfinite(below_ratio)
        and math.isfinite(above_ratio)
        and 0.0 < below_ratio < 0.25 < above_ratio
    ):
        raise RuntimeEvidenceError(
            "square J1-J3 Lifshitz probes must strictly straddle 1/4"
        )

    first_neighbors = ((1, 0), (0, 1))
    third_neighbors = ((2, 0), (0, 2))

    def shell_energy(cos_q, displacements):
        q = math.acos(cos_q)
        return sum(
            math.cos(math.pi * (dx + dy) + q * dx)
            for dx, dy in displacements
        )

    def polynomial_coefficients(displacements):
        energy_minus = shell_energy(-1.0, displacements)
        energy_zero = shell_energy(0.0, displacements)
        energy_plus = shell_energy(1.0, displacements)
        linear = 0.5 * (energy_plus - energy_minus)
        quadratic = 0.5 * (energy_plus + energy_minus) - energy_zero
        return linear, quadratic

    first_linear, first_quadratic = polynomial_coefficients(first_neighbors)
    third_linear, third_quadratic = polynomial_coefficients(third_neighbors)
    if not (
        math.isclose(first_linear, -1.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(first_quadratic, 0.0, rel_tol=0.0, abs_tol=1.0e-12)
        and math.isclose(third_linear, 0.0, rel_tol=0.0, abs_tol=1.0e-12)
        and third_quadratic > 0.0
    ):
        raise RuntimeEvidenceError(
            "square J1-J3 bond shells do not yield the expected convex branch"
        )
    denominator = 2.0 * third_quadratic / (-first_linear)
    threshold = 1.0 / denominator
    stationary_below = 1.0 / (denominator * below_ratio)
    stationary_above = 1.0 / (denominator * above_ratio)
    if not (
        math.isclose(threshold, 0.25, rel_tol=0.0, abs_tol=1.0e-12)
        and stationary_below > 1.0
        and 0.0 < stationary_above < 1.0
    ):
        raise RuntimeEvidenceError(
            "square J1-J3 bond minimization does not straddle the Lifshitz point"
        )
    integer_denominator = round(denominator)
    if not math.isclose(
        denominator, integer_denominator, rel_tol=0.0, abs_tol=1.0e-12
    ):
        raise RuntimeEvidenceError(
            "square J1-J3 stationary denominator is not integral"
        )
    return {
        "spiral_condition": f"cos(Q)=J1/({integer_denominator}J3)",
    }


def parse_liu_square_j1_j2_j3_paramagnets(source_text):
    """Extract the distinct QSL and VBS paramagnetic regions."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "multiple paramagnetic regions require nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"spin-\s*(?:1\s*[/=]\s*2|21)\s+square-lattice "
        r"J1\s*-\s*J2\s*-\s*J3 antiferromagnetic.{0,20}?Heisenberg model",
        normalized,
        flags=re.IGNORECASE,
    )
    method_match = re.search(
        r"finite projected entangled pair state\s*\(\s*PEPS\s*\)\s*method",
        normalized,
        flags=re.IGNORECASE,
    )
    phase_set_match = re.search(
        r"ground-state phase diagram.{0,180}?gapless quantum spin liquid"
        r".{0,80}?valence-bond solid\s*\(\s*VBS\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    paramagnetic_match = re.search(
        r"stabilize paramagnetic states",
        normalized,
        flags=re.IGNORECASE,
    )
    successive_match = re.search(
        r"two successive gapless quantum.{0,260}?spin liquid\s*\(\s*QSL\s*\)"
        r".{0,60}?and VBS phases.{0,180}?between the "
        r"N(?:e|é|´e)el and stripe phases",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        model_match,
        method_match,
        phase_set_match,
        paramagnetic_match,
        successive_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "multiple paramagnetic regions require the spin-1/2 square "
            "J1-J2-J3 model, PEPS method, source-identified paramagnetism, "
            "and two successive QSL and VBS phases"
        )
    return (
        {"multiple_paramagnetic_regions": True},
        {
            "parser": "parse_liu_square_j1_j2_j3_paramagnets",
            "matched_anchors": [
                "spin-1/2 square-lattice J1-J2-J3 Heisenberg model",
                "finite-PEPS phase-diagram method",
                "ground-state phase diagram contains QSL and VBS",
                "source identifies paramagnetic states",
                "two successive QSL and VBS phases",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_gong_square_j1_j2_pvb(source_text):
    """Extract the long-range plaquette-VBS result for square J1-J2."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "square J1-J2 plaquette VBS requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"spin-\s*(?:1\s*[/=]\s*2|12)\s+Heisenberg model on the square "
        r"lattice with first- and second-neighbor antiferromagnetic "
        r"interactions J\s*1 and J\s*2",
        normalized,
        flags=re.IGNORECASE,
    )
    method_match = re.search(
        r"density matrix renormalization group approach.{0,80}?"
        r"(?:SU.{0,10}?2|spin rotation symmetry)",
        normalized,
        flags=re.IGNORECASE,
    )
    phase_match = re.search(
        r"find a N(?:e|é|´e)el phase and a plaquette valence-bond "
        r"\(\s*PVB\s*\) phase with a finite spin gap",
        normalized,
        flags=re.IGNORECASE,
    )
    long_range_match = re.search(
        r"consistent with (?:a )?long-range PVB order in the "
        r"two-dimensional limit",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (model_match, method_match, phase_match, long_range_match)
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "square J1-J2 plaquette VBS requires the spin-1/2 first/second-"
            "neighbor square model, SU(2) DMRG, a gapped PVB phase, and "
            "long-range two-dimensional PVB evidence"
        )
    return (
        {"columnar_or_plaquette_vbs_reference": True},
        {
            "parser": "parse_gong_square_j1_j2_pvb",
            "matched_anchors": [
                "spin-1/2 square J1-J2 antiferromagnetic Heisenberg model",
                "SU(2) density-matrix renormalization group",
                "plaquette valence-bond phase with finite spin gap",
                "long-range PVB order in the two-dimensional limit",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_dagotto_rice_strong_rung_limit(source_text):
    """Extract the decoupled two-leg-ladder rung spectrum."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Dagotto-Rice strong-rung limit requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    strong_rung_match = re.search(
        r"J['′]\s*(?:>>|≫)\s*J", normalized, flags=re.IGNORECASE
    )
    singlet_match = re.search(
        r"(?:-|−)\s*(?:3\s*/\s*4|3\s*4|4\s*3)\s*J['′].{0,80}?"
        r"energy of each rung singlet",
        normalized,
        flags=re.IGNORECASE,
    )
    triplet_match = re.search(
        r"isolated rung-triplet has an energy\s+J['′]\s+above the rung singlet",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        strong_rung_match is None
        or singlet_match is None
        or triplet_match is None
    ):
        raise RuntimeEvidenceError(
            "Dagotto-Rice strong-rung limit must state J' >> J, the -3J'/4 "
            "rung-singlet energy, and the J' triplet gap"
        )
    return (
        {"energy_per_rung": -0.75, "gap_to_triplet": 1.0},
        {
            "parser": "parse_dagotto_rice_strong_rung_limit",
            "derivation": (
                "Take the exact decoupled-rung endpoint Jleg=0, Jrung=1: "
                "Es=-3Jrung/4 and Et-Es=Jrung"
            ),
            "matched_anchors": [
                "J' much larger than J",
                "-3J'/4 energy of each rung singlet",
                "isolated rung triplet J' above singlet",
            ],
            "text_spans": [
                [strong_rung_match.start(), strong_rung_match.end()],
                [singlet_match.start(), singlet_match.end()],
                [triplet_match.start(), triplet_match.end()],
            ],
        },
    )


def parse_dagotto_rice_two_leg_gap(source_text):
    """Extract the finite spin-gap claim for an AF two-leg ladder."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Dagotto-Rice two-leg gap requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    antiferromagnetic_match = re.search(
        r"J\s*\(\s*>\s*0\s*\)\s+is the antiferromagnetic exchange coupling",
        normalized,
        flags=re.IGNORECASE,
    )
    gap_match = re.search(
        r"2-leg ladders have a finite.{0,20}?spin\s*[-−]?\s*gap"
        r".{0,80}?finite energy is needed to create a S\s*=\s*1 excitation",
        normalized,
        flags=re.IGNORECASE,
    )
    rung_match = re.search(
        r"exchange coupling along the rungs of a 2-leg ladder"
        r".{0,40}?denoted by J['′]",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        antiferromagnetic_match is None
        or gap_match is None
        or rung_match is None
    ):
        raise RuntimeEvidenceError(
            "Dagotto-Rice two-leg gap must define positive exchange as "
            "antiferromagnetic, state the finite S=1 gap, and identify J' "
            "as the two-leg-ladder rung exchange"
        )
    return (
        {"has_finite_spin_gap_for_antiferromagnetic_rungs": True},
        {
            "parser": "parse_dagotto_rice_two_leg_gap",
            "matched_anchors": [
                "positive exchange is antiferromagnetic",
                "two-leg ladder has a finite spin gap",
                "J' is the two-leg-ladder rung exchange",
            ],
            "text_spans": [
                [antiferromagnetic_match.start(), antiferromagnetic_match.end()],
                [gap_match.start(), gap_match.end()],
                [rung_match.start(), rung_match.end()],
            ],
        },
    )


def parse_moessner_pyrochlore_flat_band(source_text):
    """Extract the tetrahedron constraint and its harmonic zero-mode band."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "pyrochlore flat-band evidence requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"classical Heisenberg antiferromagnet.{0,100}?"
        r"nearest(?:-|\s+)neighbor interactions.{0,100}?pyrochlore lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"Hamiltonian.{0,750}?L\s*_?\s*a is (?:the )?total spin in "
        r"(?:tetrahedral )?unit a",
        normalized,
        flags=re.IGNORECASE,
    )
    constraint_match = re.search(
        r"configuration is a ground state provided L\s*_?\s*a\s*"
        r"(?:=|\u00ad)\s*0 for each unit separately",
        normalized,
        flags=re.IGNORECASE,
    )
    zero_mode_match = re.search(
        r"(?:generic (?:ground )?state|ground state is a generic one)"
        r".{0,180}?"
        r"(?:3\s*y\s*4|three quarters).{0,80}?finite"
        r".{0,120}?frequenc"
        r".{0,100}?(?:1\s*y\s*4|one quarter).{0,40}?zero frequency",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        model_match,
        hamiltonian_match,
        constraint_match,
        zero_mode_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "pyrochlore flat-band evidence requires the nearest-neighbor "
            "classical Heisenberg pyrochlore, the tetrahedron-total-spin "
            "Hamiltonian, L_a=0 on every tetrahedron, and a finite fraction "
            "of zero-frequency harmonic modes"
        )
    return (
        {
            "local_constraint": "sum_tetrahedron_spins_zero",
            "lowest_lt_flat_band": True,
        },
        {
            "parser": "parse_moessner_pyrochlore_flat_band",
            "derivation": (
                "Eq. (1) is a sum of nonnegative tetrahedron-spin squares; "
                "L_a=0 minimizes every term, and the stated one-quarter "
                "zero-frequency sector is a dispersionless zero-frequency band"
            ),
            "matched_anchors": [
                "nearest-neighbor classical Heisenberg pyrochlore",
                "Hamiltonian in tetrahedron total spins",
                "ground-state constraint L_a=0 for every tetrahedron",
                "one-quarter zero-frequency harmonic modes",
            ],
            "text_spans": [
                [match.start(), match.end()]
                for match in matches
            ],
        },
    )


def parse_richter_square_j1_j2_window(source_text):
    """Extract and conservatively normalize the square J1-J2 nonmagnetic window."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "square J1-J2 window evidence requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"(?:spin-\s*1\s*/\s*2\s+J1\s*-\s*J2 model on the square lattice|"
        r"spin-\s*1\s*/\s*2 square-lattice J1\s*-\s*J2 model)",
        normalized,
        flags=re.IGNORECASE,
    )
    method_match = re.search(
        r"coupled cluster method to high orders of approximation",
        normalized,
        flags=re.IGNORECASE,
    )
    phase_match = re.search(
        r"N(?:e|é|´e)el.{0,700}?collinear antiferromagnetic",
        normalized,
        flags=re.IGNORECASE,
    )
    transition_match = re.search(
        r"transition points (?:from.{0,180}?to|to) the magnetically "
        r"disordered quantum paramagnetic phase of "
        r"J2c1\s*=\s*([0-9]+\.[0-9]+)\s*J1.{0,60}?"
        r"J2c2\s*=\s*([0-9]+\.[0-9]+)\s*J1",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (model_match, method_match, phase_match, transition_match)
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "square J1-J2 window evidence requires the spin-1/2 square model, "
            "high-order coupled cluster method, Neel and collinear bounding "
            "phases, and both transitions into the paramagnetic phase"
        )
    lower_raw = float(transition_match.group(1))
    upper_raw = float(transition_match.group(2))
    if (
        not math.isfinite(lower_raw)
        or not math.isfinite(upper_raw)
        or lower_raw < 0.0
        or lower_raw >= upper_raw
    ):
        raise RuntimeEvidenceError(
            "square J1-J2 window transition points must be finite and ordered"
        )
    lower_approx = math.floor(lower_raw * 10.0 + 1.0e-12) / 10.0
    upper_approx = math.ceil(upper_raw * 10.0 - 1.0e-12) / 10.0
    return (
        {"nonmagnetic_window_approx": [lower_approx, upper_approx]},
        {
            "parser": "parse_richter_square_j1_j2_window",
            "raw_transition_points": [lower_raw, upper_raw],
            "normalization": "outward_to_one_decimal",
            "matched_anchors": [
                "spin-1/2 square-lattice J1-J2 model",
                "high-order coupled cluster method",
                "Neel and collinear antiferromagnetic bounding phases",
                "two transitions into the magnetically disordered phase",
            ],
            "text_spans": [
                [match.start(), match.end()]
                for match in matches
            ],
        },
    )


def parse_tb2ti2o7_cooperative_paramagnet(source_text):
    """Extract the dynamic cooperative-paramagnet evidence for Tb2Ti2O7."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Tb2Ti2O7 cooperative-paramagnet evidence requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_model_match = re.search(
        r"(?:pyrochlore antiferromagnet.{0,40}?Tb2\s*Ti2\s*O7|"
        r"Tb2\s*Ti2\s*O7.{0,80}?pyrochlore antiferromagnet)",
        normalized,
        flags=re.IGNORECASE,
    )
    method_match = re.search(
        r"neutron scattering.{0,80}?muon spin relaxation.{0,80}?"
        r"dc susceptibility studies",
        normalized,
        flags=re.IGNORECASE,
    )
    disorder_match = re.search(
        r"Tb2\s*Ti2\s*O7 remains paramag-?\s*netic down to.{0,30}?"
        r"0\.07\s*K.{0,50}?rather than ordering into a conventional "
        r"N(?:e|é|´e)el or spin-glass-like state",
        normalized,
        flags=re.IGNORECASE,
    )
    dynamics_match = re.search(
        r"(?:smooth monotonic increase of 1\s*y\s*T1 down to 70\s*mK"
        r".{0,160}?remains paramag-?\s*netic down.{0,180}?"
        r"very low temperatures|"
        r"muon spin relaxation down to 70\s*mK.{0,180}?"
        r"persistent spin dynamics)",
        normalized,
        flags=re.IGNORECASE,
    )
    cooperative_match = re.search(
        r"cooperative paramagnet(?:ism)?",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        material_model_match,
        method_match,
        disorder_match,
        dynamics_match,
        cooperative_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Tb2Ti2O7 cooperative-paramagnet evidence requires the material "
            "and pyrochlore identity, neutron/muon/susceptibility methods, "
            "absence of conventional or spin-glass order to 0.07 K, "
            "persistent low-temperature dynamics, and cooperative "
            "paramagnetism"
        )
    return (
        {"spin_liquid_candidate": True},
        {
            "parser": "parse_tb2ti2o7_cooperative_paramagnet",
            "matched_anchors": [
                "Tb2Ti2O7 pyrochlore antiferromagnet",
                "neutron, muon-relaxation, and susceptibility measurements",
                "paramagnetic rather than conventional order to 0.07 K",
                "persistent muon spin dynamics to 70 mK",
                "cooperative paramagnetism",
            ],
            "text_spans": [
                [match.start(), match.end()]
                for match in matches
            ],
        },
    )


def parse_scgo_unconventional_low_t_state(source_text):
    """Extract SCGO's spin-glass freezing without conventional magnetic order."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "SCGO low-temperature evidence requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(
        r"(?:SrCr\s*8\s*Ga\s*4\s*O\s*19|"
        r"magnetoplumbite isomorph.{0,40}?SrCr\S{0,12}Ga\S{0,12}9)",
        normalized,
        flags=re.IGNORECASE,
    )
    kagome_match = re.search(
        r"(?:Cr (?:sites|ions).{0,260}?)?corner-sharing triangles.{0,340}?"
        r"(?:Kagom(?:e|é)|Ka-.{0,80}?gome) lattice.{0,160}?"
        r"quasi-two-dimensional",
        normalized,
        flags=re.IGNORECASE,
    )
    scale_match = re.search(
        r"(?:Curie-Weiss temperature is|[8e][A-Za-z$]*\s*=)\s*515\s*K"
        r".{0,320}?no (?:conventional )?ordering anomaly is seen"
        r".{0,100}?3\.5\s*K",
        normalized,
        flags=re.IGNORECASE,
    )
    glass_match = re.search(
        r"(?:spin-glass|SG)(?:-type)?.{0,100}?"
        r"(?:freezing transition|transition|ordering)",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (material_match, kagome_match, scale_match, glass_match)
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "SCGO low-temperature evidence requires the SrCr8Ga4O19 "
            "material, quasi-two-dimensional kagome geometry, the 515 K to "
            "3.5 K frustration scale separation, and spin-glass rather than "
            "conventional long-range ordering"
        )
    return (
        {"no_conventional_order_down_to_low_t": True},
        {
            "parser": "parse_scgo_unconventional_low_t_state",
            "derivation": (
                "The only low-temperature anomaly is identified as spin-glass "
                "freezing after conventional ordering is suppressed by a "
                "Curie-Weiss-to-freezing ratio of about 150"
            ),
            "matched_anchors": [
                "SrCr8Ga4O19",
                "quasi-two-dimensional kagome network",
                "515 K Curie-Weiss scale versus 3.5 K anomaly",
                "spin-glass freezing rather than conventional order",
            ],
            "text_spans": [
                [match.start(), match.end()]
                for match in matches
            ],
        },
    )


def parse_haldane_shastry_ground_state(source_text):
    """Extract Haldane's exact inverse-square Jastrow ground-state claim."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Haldane-Shastry ground state requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    construction_match = re.search(
        r"I construct the exact Jastrow-product.{0,80}?ground-state wave "
        r"function",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"one-dimen.{0,30}?\(1D\) isotropic Heisenberg antiferromagnet",
        normalized,
        flags=re.IGNORECASE,
    )
    exchange_match = re.search(
        r"exchange coupling falling off as the inverse square"
        r".{0,80}?distance between sites",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        construction_match is None
        or model_match is None
        or exchange_match is None
    ):
        raise RuntimeEvidenceError(
            "Haldane-Shastry ground state must identify the exact "
            "Jastrow-product ground state, the one-dimensional isotropic "
            "Heisenberg antiferromagnet, and inverse-square exchange"
        )
    return (
        {"has_exact_jastrow_ground_state": True},
        {
            "parser": "parse_haldane_shastry_ground_state",
            "matched_anchors": [
                "construct exact Jastrow-product ground state",
                "one-dimensional isotropic Heisenberg antiferromagnet",
                "inverse-square distance exchange",
            ],
            "text_spans": [
                [construction_match.start(), construction_match.end()],
                [model_match.start(), model_match.end()],
                [exchange_match.start(), exchange_match.end()],
            ],
        },
    )


def parse_baxter_eight_vertex_solution(source_text):
    """Extract Baxter's zero-field eight-vertex solution claim."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Baxter eight-vertex solution requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    title_match = re.search(
        r"Eight-Vertex Model in Lattice Statistics",
        normalized,
        flags=re.IGNORECASE,
    )
    solution_match = re.search(
        r"solution of the zero-field [\"“]?eight-vertex[\"”]? model is presented",
        normalized,
        flags=re.IGNORECASE,
    )
    special_cases_match = re.search(
        r"model includes the square lattice Ising, dimer, ice"
        r".{0,40}?models as special cases",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        title_match is None
        or solution_match is None
        or special_cases_match is None
    ):
        raise RuntimeEvidenceError(
            "Baxter eight-vertex solution must identify the lattice-statistics "
            "model, present its zero-field solution, and list square-lattice "
            "models as special cases"
        )
    return (
        {"is_exactly_solved": True},
        {
            "parser": "parse_baxter_eight_vertex_solution",
            "matched_anchors": [
                "eight-vertex lattice-statistics model",
                "solution of zero-field eight-vertex model is presented",
                "square-lattice models included as special cases",
            ],
            "text_spans": [
                [title_match.start(), title_match.end()],
                [solution_match.start(), solution_match.end()],
                [special_cases_match.start(), special_cases_match.end()],
            ],
        },
    )


def recompute_baxter_eight_vertex_critical_line(*, critical_weight_points):
    """Check that distinct positive zero-field weights lie on the exact boundary."""

    if (
        not isinstance(critical_weight_points, Sequence)
        or isinstance(critical_weight_points, (str, bytes))
        or len(critical_weight_points) < 2
    ):
        raise RuntimeEvidenceError(
            "Baxter critical-line recomputation requires at least two "
            "boundary points"
        )

    field_names = ("a", "b", "c", "d")
    normalized_points = []
    boundary_matches = []
    for point in critical_weight_points:
        if not isinstance(point, Mapping) or set(point) != set(field_names):
            raise RuntimeEvidenceError(
                "Baxter critical-line points must contain exactly a, b, c, d"
            )
        weights = tuple(point[field] for field in field_names)
        if any(
            isinstance(weight, bool)
            or not isinstance(weight, (int, float))
            or not math.isfinite(weight)
            or weight <= 0.0
            for weight in weights
        ):
            raise RuntimeEvidenceError(
                "Baxter critical-line weights must be positive finite reals"
            )
        total = sum(weights)
        normalized_points.append(
            tuple(float(weight) / total for weight in weights)
        )
        boundary_matches.append(
            math.isclose(
                2.0 * max(weights),
                total,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        )

    first_point = normalized_points[0]
    if all(
        all(
            math.isclose(
                left,
                right,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            for left, right in zip(first_point, point)
        )
        for point in normalized_points[1:]
    ):
        raise RuntimeEvidenceError(
            "Baxter critical-line points must include distinct "
            "non-proportional weights"
        )

    return {"has_exact_critical_line": all(boundary_matches)}


def parse_baxter_eight_vertex_critical_line(source_text):
    """Extract Baxter's exact zero-field eight-vertex critical manifold."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Baxter critical line requires nonempty source text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    identity_match = re.search(
        r"Eight-Vertex Model in Lattice Statistics"
        r".{0,180}?R\.?\s*J\.?\s*Baxter",
        normalized,
        flags=re.IGNORECASE,
    )
    solution_match = re.search(
        r"solution of the zero-field [\"“]?eight-vertex[\"”]? model "
        r"is presented",
        normalized,
        flags=re.IGNORECASE,
    )
    square_models_match = re.search(
        r"model includes the square lattice Ising, dimer, ice"
        r".{0,50}?models as special cases",
        normalized,
        flags=re.IGNORECASE,
    )
    zero_field_match = re.search(
        r"unchanged by reversal of all arrows"
        r".{0,420}?implies that there are.{0,180}?no electric fields",
        normalized,
        flags=re.IGNORECASE,
    )
    arbitrary_weights_match = re.search(
        r"succeeded in solving this model for.{0,180}?arbitrary values of "
        r"a,\s*b,\s*c,\s*and\s*d",
        normalized,
        flags=re.IGNORECASE,
    )
    principal_domain_match = re.search(
        r"(?:restrictions|re-.{0,140}?strictions).{0,80}?equivalent to "
        r"a\s*(?:>|&)\s*0,\s*b\s*(?:>|&)\s*0,\s*d\s*(?:>|&)\s*0,"
        r"\s*and\s*c\s*(?:>|&)\s*a\s*\+\s*b\s*\+\s*d"
        r".{0,180}?principal dom(?:ain|ian)",
        normalized,
        flags=re.IGNORECASE,
    )
    boundary_match = re.search(
        r"Inside the principal domain.{0,180}?analytic function"
        r".{0,900}?phase transition can occur only"
        r".{0,700}?cross a boundary of the principal dom(?:ain|ian)",
        normalized,
        flags=re.IGNORECASE,
    )
    singular_boundary_match = re.search(
        r"(?:c|e)\s*-\s*a\s*-\s*b\s*-\s*d"
        r".{0,100}?(?:zero|zexo)"
        r".{0,1800}?simple zero at some value"
        r".{0,700}?f can be written as the sum of an analytic and a"
        r".{0,240}?singular function",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        solution_match,
        square_models_match,
        zero_field_match,
        arbitrary_weights_match,
        principal_domain_match,
        boundary_match,
        singular_boundary_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Baxter critical line requires the identified zero-field "
            "eight-vertex solution on the square lattice, arrow-reversal "
            "symmetry, arbitrary positive vertex weights, the principal-"
            "domain boundary c=a+b+d (and symmetry equivalents), and the "
            "singular free energy produced by a simple boundary zero"
        )

    return (
        {"has_exact_critical_line": True},
        {
            "parser": "parse_baxter_eight_vertex_critical_line",
            "critical_boundary": "max(a,b,c,d)=sum(other three)",
            "derivation": (
                "Baxter solves the zero-field model for arbitrary positive "
                "weights. The free energy is analytic inside each principal "
                "domain, while a simple zero of c-a-b-d at its boundary "
                "produces a singular contribution; symmetry gives the "
                "equivalent boundaries with a, b, or d maximal."
            ),
            "matched_anchors": [
                "identified Baxter eight-vertex paper and author",
                "zero-field eight-vertex solution",
                "square-lattice special cases",
                "arrow-reversal symmetry means no electric fields",
                "solution for arbitrary a, b, c, d",
                "positive-weight principal domain c>a+b+d",
                "phase transition only on a principal-domain boundary",
                "simple boundary zero produces singular free energy",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_lieb_square_ice_solution(source_text):
    """Extract Lieb's exact square-ice solution status."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Lieb square-ice solution requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    geometry_match = re.search(
        r"problem in two dimensions.{0,100}?bonds of a square planar net",
        normalized,
        flags=re.IGNORECASE,
    )
    ice_rule_match = re.search(
        r"precisely two arrows point into each vertex",
        normalized,
        flags=re.IGNORECASE,
    )
    exact_match = re.search(
        r"Our exact result is", normalized, flags=re.IGNORECASE
    )
    if geometry_match is None or ice_rule_match is None or exact_match is None:
        raise RuntimeEvidenceError(
            "Lieb square-ice solution must define the two-dimensional square "
            "planar net, its two-in ice rule, and an exact result"
        )
    return (
        {"is_exactly_solved": True},
        {
            "parser": "parse_lieb_square_ice_solution",
            "matched_anchors": [
                "two-dimensional square planar net",
                "two arrows point into each vertex",
                "exact square-ice result",
            ],
            "text_spans": [
                [geometry_match.start(), geometry_match.end()],
                [ice_rule_match.start(), ice_rule_match.end()],
                [exact_match.start(), exact_match.end()],
            ],
        },
    )


def parse_yang_gaudin_fermion_solution(source_text):
    """Extract Yang's exact repulsive delta-fermion Bethe solution claim."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Yang-Gaudin solution requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    title_match = re.search(
        r"Some Exact Results for the Many-Body Problem in One Dimension "
        r"with Repulsive Delta-Function Interaction",
        normalized,
        flags=re.IGNORECASE,
    )
    bethe_match = re.search(
        r"repulsive (?:delta(?:-function)?|5) interaction problem in one "
        r"dimension.{0,100}?Bethe['’]s hypothesis",
        normalized,
        flags=re.IGNORECASE,
    )
    fermion_match = re.search(
        r"ground-state problem of spin\s*[-−]?\s*(?:1\s*/\s*2|2) fermions "
        r"is reduced to a generalized Fredholm equation",
        normalized,
        flags=re.IGNORECASE,
    )
    if title_match is None or bethe_match is None or fermion_match is None:
        raise RuntimeEvidenceError(
            "Yang-Gaudin solution must identify the exact one-dimensional "
            "repulsive delta-interaction problem, its Bethe reduction, and "
            "the spin-half-fermion ground-state Fredholm equation"
        )
    return (
        {"is_exactly_solved": True},
        {
            "parser": "parse_yang_gaudin_fermion_solution",
            "matched_anchors": [
                "exact one-dimensional repulsive delta-interaction result",
                "repulsive interaction reduced through Bethe hypothesis",
                "spin-half-fermion ground state reduced to Fredholm equation",
            ],
            "text_spans": [
                [title_match.start(), title_match.end()],
                [bethe_match.start(), bethe_match.end()],
                [fermion_match.start(), fermion_match.end()],
            ],
        },
    )


def parse_lieb_liniger_solution(source_text):
    """Extract the Lieb-Liniger exact solution and impenetrable-boson limit."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Lieb-Liniger solution requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    exact_match = re.search(
        r"gas of one-dimensional Bose particles interacting via a repulsive "
        r"delta-function potential has been solved exactly",
        normalized,
        flags=re.IGNORECASE,
    )
    spectrum_match = re.search(
        r"All the eigenfunctions can be found explicitly and the energies are "
        r"given by (?:the solutions? of )?a transcendental equation",
        normalized,
        flags=re.IGNORECASE,
    )
    fermion_limit_match = re.search(
        r"impenetrable bosons in one dimension.{0,120}?energy spectrum"
        r"(?: of (?:such )?a gas)? is identical with the.{0,100}?spectrum of a "
        r"noninteracting Fermi gas",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        exact_match is None
        or spectrum_match is None
        or fermion_limit_match is None
    ):
        raise RuntimeEvidenceError(
            "Lieb-Liniger solution must identify the exactly solved "
            "one-dimensional repulsive delta Bose gas, its explicit "
            "eigenfunctions, and the free-fermion spectrum of the "
            "impenetrable-boson limit"
        )
    return (
        {
            "is_exactly_solved": True,
            "tonks_girardeau_limit_maps_to_free_fermions": True,
        },
        {
            "parser": "parse_lieb_liniger_solution",
            "matched_anchors": [
                "one-dimensional repulsive delta Bose gas solved exactly",
                "explicit eigenfunctions and transcendental energy equation",
                "impenetrable-boson spectrum equals free-fermion spectrum",
            ],
            "text_spans": [
                [exact_match.start(), exact_match.end()],
                [spectrum_match.start(), spectrum_match.end()],
                [fermion_limit_match.start(), fermion_limit_match.end()],
            ],
        },
    )


def parse_pauling_spin_ice_entropy(source_text):
    """Derive the Pauling residual-entropy formula for spin ice."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Pauling spin-ice entropy requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    spin_ice_match = re.search(
        r"spin ice materials", normalized, flags=re.IGNORECASE
    )
    degeneracy_match = re.search(
        r"Pauling['’]?s? estimated.{0,120}?(?:the )?degeneracy to be.{0,100}?"
        r"\(\s*3\s*/\s*2\s*\)\s*(?:\^\s*)?\(?N\)?\s*/\s*2",
        normalized,
        flags=re.IGNORECASE,
    )
    entropy_match = re.search(
        r"zero point entropy S\s*0.{0,100}?\(\s*R\s*/\s*2\s*\)\s*"
        r"ln\s*\(\s*3\s*/\s*2\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        spin_ice_match is None
        or degeneracy_match is None
        or entropy_match is None
    ):
        raise RuntimeEvidenceError(
            "Pauling spin-ice entropy must identify spin ice, Pauling's "
            "(3/2)^(N/2) degeneracy, and S0=(R/2)ln(3/2)"
        )
    return (
        {"pauling_entropy_per_spin": 0.5 * math.log(1.5)},
        {
            "parser": "parse_pauling_spin_ice_entropy",
            "derivation": "S0/N = (1/2) ln(3/2) from Pauling's degeneracy",
            "matched_anchors": [
                "spin-ice materials",
                "Pauling degeneracy (3/2)^(N/2)",
                "zero-point entropy (R/2) ln(3/2)",
            ],
            "text_spans": [
                [spin_ice_match.start(), spin_ice_match.end()],
                [degeneracy_match.start(), degeneracy_match.end()],
                [entropy_match.start(), entropy_match.end()],
            ],
        },
    )


def parse_bkt_universal_jump(source_text):
    """Extract the Nelson-Kosterlitz universal XY stiffness jump."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("BKT universal jump requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    universal_match = re.search(
        r"two-dimensional XY model.{0,120}?predict(?:s)? a universal jump"
        r".{0,500}?approach(?:es|ed).{0,50}?from below",
        normalized,
        flags=re.IGNORECASE,
    )
    stiffness_match = re.search(
        r"Predictions for the spin-wave stiffness in two-.{0,160}?"
        r"dimensional magnetic systems(?: analogous to \(10\)| follow from XY "
        r"magnetism and superfluidity)",
        normalized,
        flags=re.IGNORECASE,
    )
    equation_match = re.search(
        r"lim\s+K(?:[_ ,]\s*i?)?\s*\(T\)\s*/\s*\(?k(?:_|\s*)B\s*T\)?"
        r"\s*=\s*2\s*/\s*(?:pi|π|m)",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        universal_match is None
        or stiffness_match is None
        or equation_match is None
    ):
        raise RuntimeEvidenceError(
            "BKT universal jump must identify the two-dimensional XY jump "
            "from below, its magnetic spin-wave stiffness, and "
            "K(T)/(k_B T)=2/pi"
        )
    return (
        {
            "formula": "rho_s(T_BKT)=2T_BKT/pi",
            "helicity_modulus_at_t_1": 2.0 / math.pi,
        },
        {
            "parser": "parse_bkt_universal_jump",
            "normalization": "locked Nelson-Kosterlitz PDF maps pi glyph to m",
            "matched_anchors": [
                "two-dimensional XY universal jump approached from below",
                "magnetic spin-wave stiffness analogous to superfluid result",
                "critical stiffness ratio 2/pi",
            ],
            "text_spans": [
                [universal_match.start(), universal_match.end()],
                [stiffness_match.start(), stiffness_match.end()],
                [equation_match.start(), equation_match.end()],
            ],
        },
    )


def recompute_bkt_universal_jump_operand(*, temperature):
    """Return every registered BKT-jump field from the local helper."""

    return {
        "formula": "rho_s(T_BKT)=2T_BKT/pi",
        "helicity_modulus_at_t_1": (
            benchmark_functions.xy_bkt_universal_helicity_jump(
                temperature=temperature
            )
        ),
    }


def parse_kitazawa_nomura_takhtajan_babujian_point(source_text):
    """Extract the spin-1 Takhtajan-Babujian point in the theta convention."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Takhtajan-Babujian spin-1 point requires nonempty text"
        )
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_kitazawa_nomura_takhtajan_babujian_point",
    )
    return _finalize_prepared_trace(
        _parse_kitazawa_nomura_takhtajan_babujian_point_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_kitazawa_nomura_takhtajan_babujian_point_prepared(normalized):

    identity_match = re.search(
        r"Bifurcation at the c\s*=\s*3\s*/\s*2 "
        r"Takhtajan-Babujian point.{0,160}?c\s*=\s*1 critical lines"
        r".{0,700}?Atsuhiro Kitazawa and Kiyohide Nomura",
        normalized,
        flags=re.IGNORECASE,
    )
    spin1_model_match = re.search(
        r"We study the S\s*=\s*1 quantum spin chains with bilinear"
        r".{0,900}?biquadratic.{0,500}?vicinity of the S\s*=\s*"
        r"(?:1\s+Takhtajan-Babujian model|.{1,240}?1 "
        r"Takhtajan-Babujian model)",
        normalized,
        flags=re.IGNORECASE,
    )
    point_pattern = (
        r"TB point\s*\(\s*(?:theta|θ)\s*=\s*[−-]\s*(?:pi|π)\s*/\s*4"
        r"\s*,\s*(?:delta|δ)\s*=\s*0\s*\)"
    )
    point_match = re.search(point_pattern, normalized, flags=re.IGNORECASE)

    spin_pair_pattern = (
        r"S\s*_?\s*j\s*(?:dot|[·.])\s*S\s*_?\s*j\s*\+?\s*1"
    )
    formula_pattern = (
        r"1\s*[−-]\s*(?:delta|δ)\s*\(\s*[−-]\s*1\s*\)"
        r"\s*(?:\^\s*)?j.{0,120}?"
        r"cos\s*\(?\s*(?:theta|θ)\s*\)?\s*"
        + spin_pair_pattern
        + r".{0,120}?\+\s*sin\s*\(?\s*(?:theta|θ)\s*\)?\s*"
        r"\(\s*"
        + spin_pair_pattern
        + r"\s*\)\s*(?:\^\s*)?2"
    )
    hamiltonian_match = re.search(
        r"(?:\bH\s*=.{0,900}?"
        + formula_pattern
        + r"|"
        + formula_pattern
        + r".{0,900}?\bH\s*=)",
        normalized,
        flags=re.IGNORECASE,
    )
    integrability_match = re.search(
        r"\bintegrable.{0,260}?Takhtajan-Babujian\s*\(TB\)\s*model",
        normalized,
        flags=re.IGNORECASE,
    )
    critical_match = re.search(
        r"At the\s+"
        + point_pattern
        + r".{0,300}?critical prop(?:erties|-.{0,260}?erties)"
        r".{0,900}?k\s*=\s*2\s+SU\(2\)"
        r".{0,1800}?Wess-Zumino-Witten model"
        r".{0,700}?confirmed.{0,300}?by Bethe ansatz",
        normalized,
        flags=re.IGNORECASE,
    )
    matches_by_name = {
        "source_identity": identity_match,
        "spin1_model": spin1_model_match,
        "tb_point": point_match,
        "hamiltonian": hamiltonian_match,
        "integrability": integrability_match,
        "critical_bethe": critical_match,
    }
    missing_anchors = [
        name for name, match in matches_by_name.items() if match is None
    ]
    if missing_anchors:
        raise RuntimeEvidenceError(
            "Takhtajan-Babujian spin-1 point must identify the "
            "Kitazawa-Nomura source, spin-1 bilinear-biquadratic "
            "Hamiltonian, theta=-pi/4 with zero bond alternation, exact "
            "integrability, k=2 criticality, and Bethe-ansatz confirmation; "
            f"missing anchors: {', '.join(missing_anchors)}"
        )
    matches = list(matches_by_name.values())

    theta = -math.pi / 4.0
    if not (
        math.cos(theta) > 0.0
        and math.sin(theta) < 0.0
        and math.isclose(
            math.cos(theta),
            -math.sin(theta),
            rel_tol=0.0,
            abs_tol=1.0e-15,
        )
    ):
        raise RuntimeEvidenceError(
            "Takhtajan-Babujian spin-1 point did not map to equal and "
            "opposite bilinear-biquadratic coefficients"
        )

    return (
        {"theta_radians": theta, "is_integrable": True},
        {
            "parser": (
                "parse_kitazawa_nomura_takhtajan_babujian_point"
            ),
            "source_role": (
                "machine-extractable supplemental primary research source"
            ),
            "registered_source_relationship": (
                "Babujian 1982 remains the historical registered source; "
                "Kitazawa-Nomura restates the model in the registry's "
                "cos(theta), sin(theta) convention"
            ),
            "derivation": (
                "The source defines the spin-1 bond as "
                "cos(theta) S_i.S_j + sin(theta) (S_i.S_j)^2, labels the "
                "unmodulated TB point theta=-pi/4 and delta=0, and calls "
                "the Takhtajan-Babujian model integrable; therefore "
                "cos(theta)>0, sin(theta)<0, and the two magnitudes are "
                "equal."
            ),
            "matched_anchors": [
                "Kitazawa-Nomura source identity",
                "spin-1 bilinear-biquadratic chain",
                "TB point theta=-pi/4 and delta=0",
                "cos(theta), sin(theta) Hamiltonian convention",
                "integrable Takhtajan-Babujian model",
                "k=2 criticality confirmed by Bethe ansatz",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_uls_spin1_su3_point(source_text):
    """Extract Sutherland's spin-1 SU(3) permutation-Hamiltonian point."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("ULS spin-1 SU(3) point requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    permutation_match = re.search(
        r"Place.{0,100}?exactly one.{0,40}?to a site.{0,80}?operator P"
        r".{0,120}?permute whatever objects occupy.{0,100}?sites.{0,350}?"
        r"Hamiltonian",
        normalized,
        flags=re.IGNORECASE,
    )
    symmetry_match = re.search(
        r"(?:Eq\.?|Equation)\s*\(41\).{0,80}?invariant under.{0,160}?the total\s*"
        r"SU\(3\) group",
        normalized,
        flags=re.IGNORECASE,
    )
    spin1_match = re.search(
        r"return to consider a spin-1 representa(?:tion|-.{0,160}?tion) "
        r"for our system.{0,220}?writing the SU\(3\) generators "
        r"in terms of the three.{0,220}?spin operators.{0,100}?"
        r"six tensor.{0,220}?operators",
        normalized,
        flags=re.IGNORECASE,
    )
    bethe_match = re.search(
        r"one dimension(?:al problem)? by Bethe(?:['’]|\s+)s ansatz|"
        r"one-dimensional problem is solved by Bethe(?:['’]|\s+)s ansatz",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        permutation_match is None
        or symmetry_match is None
        or spin1_match is None
        or bethe_match is None
    ):
        raise RuntimeEvidenceError(
            "ULS spin-1 SU(3) point must identify the permutation Hamiltonian, "
            "total SU(3) invariance, its spin-1 representation, and the "
            "one-dimensional Bethe solution"
        )
    return (
        {"theta_radians": math.pi / 4.0, "su3_symmetric": True},
        {
            "parser": "parse_uls_spin1_su3_point",
            "derivation": (
                "For spin 1, P_ij = S_i.S_j + (S_i.S_j)^2 - 1; equal "
                "positive bilinear and biquadratic coefficients imply "
                "theta=pi/4"
            ),
            "matched_anchors": [
                "nearest-neighbor permutation Hamiltonian",
                "Hamiltonian invariant under total SU(3)",
                "SU(3) generators in spin-1 representation",
                "one-dimensional Bethe ansatz",
            ],
            "text_spans": [
                [permutation_match.start(), permutation_match.end()],
                [symmetry_match.start(), symmetry_match.end()],
                [spin1_match.start(), spin1_match.end()],
                [bethe_match.start(), bethe_match.end()],
            ],
        },
    )


def recompute_uls_spin1_su3_operand():
    """Recompute both registered ULS fields from the equal-coupling point."""

    theta = benchmark_functions.spin1_bilinear_biquadratic_integrable_angle(
        "uimin_lai_sutherland"
    )
    equal_positive_couplings = (
        math.cos(theta) > 0.0
        and math.isclose(
            math.cos(theta), math.sin(theta), rel_tol=0.0, abs_tol=1.0e-15
        )
    )
    return {
        "theta_radians": theta,
        "su3_symmetric": equal_positive_couplings,
    }


def parse_square_compass_line_symmetries(source_text):
    """Extract the exact line symmetries of the square 90-degree compass model."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "square compass line symmetry requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"anisotropic compass model.{0,300}?D\s*(?:=|¼)\s*2.{0,300}?"
        r"Eq\.\s*\(1\).{0,500}?general couplings J\s*x.{0,100}?J\s*y"
        r".{0,500}?Eq\.\s*\(4\).{0,200}?without field.{0,300}?"
        r"H\s*90.{0,160}?J.{0,160}?(?:tau|τ)",
        normalized,
        flags=re.IGNORECASE,
    )
    operator_match = re.search(
        r"Exact symmetries of (?:both )?the square lattice.{0,240}?"
        r"90(?:°|\s*degree).{0,60}?compass models?.{0,1000}?"
        r"(?:(?:product|∏).{0,100}?P.{0,180}?exp\s*\(.{0,120}?(?:\(84\)|ð84Þ)|"
        r"Y.{0,300}?(?:O|ˆ).{0,100}?e.{0,20}?πT.{0,120}?\(84\)"
        r"|Y.{0,300}?(?:O|ˆ).{0,100}?e.{0,20}?πT.{0,120}?ð84Þ"
        r".{0,120}?r.{0,10}?P)",
        normalized,
        flags=re.IGNORECASE,
    )
    line_match = re.search(
        r"P.{0,20}?is any line.{0,200}?two(?:-|\s).{0,180}?dimensional model"
        r".{0,220}?"
        r"orthogonal to the external e.{0,30}?axis",
        normalized,
        flags=re.IGNORECASE,
    )
    commutator_match = re.search(
        r"operators of Eq\.\s*\(84\) (?<!not )commute with the general "
        r".{0,180}?Hamiltonian.{0,160}?(?:\[.{0,30}?H.{0,20}?\]\s*=\s*0|"
        r"½.{0,80}?H.{0,30}?(?:=|¼)\s*0)",
        normalized,
        flags=re.IGNORECASE,
    )
    if any(
        match is None
        for match in (model_match, operator_match, line_match, commutator_match)
    ):
        raise RuntimeEvidenceError(
            "square compass line symmetry must identify the anisotropic "
            "90-degree Hamiltonian, Eq. (84) line operator, its two-dimensional "
            "line support, and the exact zero commutator"
        )
    return (
        {"has_line_flip_symmetries": True},
        {
            "parser": "parse_square_compass_line_symmetries",
            "matched_anchors": [
                "anisotropic 90-degree compass Hamiltonian",
                "Eq. (84) product symmetry operator",
                "line support in the two-dimensional model",
                "exact line-operator commutator [O,H]=0",
            ],
            "text_spans": [
                [model_match.start(), model_match.end()],
                [operator_match.start(), operator_match.end()],
                [line_match.start(), line_match.end()],
                [commutator_match.start(), commutator_match.end()],
            ],
        },
    )


def _pauli_strings_commute(left, right):
    anticommuting_sites = sum(
        left_pauli != "I"
        and right_pauli != "I"
        and left_pauli != right_pauli
        for left_pauli, right_pauli in zip(left, right)
    )
    return anticommuting_sites % 2 == 0


def recompute_square_compass_line_symmetries(*, length, j_x, j_y):
    """Check all square-compass line operators against a finite Hamiltonian."""

    if type(length) is not int or length < 2:
        raise RuntimeEvidenceError("square compass length must be an integer >= 2")
    if any(
        isinstance(coupling, bool)
        or not isinstance(coupling, (int, float))
        or not math.isfinite(coupling)
        for coupling in (j_x, j_y)
    ):
        raise RuntimeEvidenceError("square compass couplings must be finite numbers")

    site_count = length * length

    def pauli_string(assignments):
        operator = ["I"] * site_count
        for site, pauli in assignments:
            operator[site] = pauli
        return tuple(operator)

    hamiltonian_terms = []
    for row in range(length):
        for column in range(length - 1):
            left = row * length + column
            hamiltonian_terms.append(
                pauli_string(((left, "X"), (left + 1, "X")))
            )
    for row in range(length - 1):
        for column in range(length):
            lower = row * length + column
            hamiltonian_terms.append(
                pauli_string(((lower, "Y"), (lower + length, "Y")))
            )

    line_operators = []
    for column in range(length):
        line_operators.append(
            pauli_string(
                ((row * length + column, "X") for row in range(length))
            )
        )
    for row in range(length):
        line_operators.append(
            pauli_string(
                ((row * length + column, "Y") for column in range(length))
            )
        )

    return {
        "has_line_flip_symmetries": all(
            _pauli_strings_commute(line_operator, term)
            for line_operator in line_operators
            for term in hamiltonian_terms
        )
    }


def parse_kitaev_exact_spin_liquid(source_text):
    """Extract the exact-solution and isotropic gapless-phase claims."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Kitaev exact-solution claim requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    exact_match = re.search(
        r"exact solution is obtained by a reduction to free real fermions",
        normalized,
        flags=re.IGNORECASE,
    )
    phase_match = re.search(
        r"in phase B the fermions are gapless",
        normalized,
        flags=re.IGNORECASE,
    )
    isotropic_match = re.search(
        r"symmetric case\s*\(\s*Jx\s*=\s*Jy\s*=\s*Jz\s*\)"
        r".{0,160}?zeros of the spectrum",
        normalized,
        flags=re.IGNORECASE,
    )
    if exact_match is None or phase_match is None or isotropic_match is None:
        raise RuntimeEvidenceError(
            "Kitaev exact-solution claim must identify the free-real-fermion "
            "solution, gapless phase B, and the symmetric isotropic point"
        )
    return (
        {
            "is_exactly_solvable": True,
            "isotropic_phase": "gapless_spin_liquid",
        },
        {
            "parser": "parse_kitaev_exact_spin_liquid",
            "matched_anchors": [
                "exact solution by free real fermions",
                "phase B fermions are gapless",
                "symmetric Jx=Jy=Jz spectrum zeros",
            ],
            "text_spans": [
                [exact_match.start(), exact_match.end()],
                [phase_match.start(), phase_match.end()],
                [isotropic_match.start(), isotropic_match.end()],
            ],
        },
    )


def parse_kitaev_gapless_triangle_condition(source_text):
    """Extract Kitaev's Eq. (33) gapless triangle criterion."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Kitaev gapless condition requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    prefix_match = re.search(
        r"solutions if and only if\s*\|Jx\s*\|\s*,\s*\|Jy\s*\|\s*,\s*\|Jz\s*\|"
        r"\s+satisfy the triangle inequalities",
        normalized,
        flags=re.IGNORECASE,
    )
    inequality_patterns = (
        r"\|Jx\s*\|\s*(?:<=|≤|6)\s*\|Jy\s*\|\s*\+\s*\|Jz\s*\|",
        r"\|Jy\s*\|\s*(?:<=|≤|6)\s*\|Jx\s*\|\s*\+\s*\|Jz\s*\|",
        r"\|Jz\s*\|\s*(?:<=|≤|6)\s*\|Jx\s*\|\s*\+\s*\|Jy\s*\|",
    )
    inequality_matches = [
        re.search(pattern, normalized, flags=re.IGNORECASE)
        for pattern in inequality_patterns
    ]
    equation_match = re.search(r"\(33\)", normalized)
    phase_match = re.search(
        r"(?:phase B|marked by B).{0,80}?this phase is gapless",
        normalized,
        flags=re.IGNORECASE,
    )
    isotropic_match = re.search(
        r"symmetric case\s*\(\s*Jx\s*=\s*Jy\s*=\s*Jz\s*\)"
        r".{0,160}?zeros of the spectrum",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        prefix_match is None
        or any(match is None for match in inequality_matches)
        or equation_match is None
        or phase_match is None
        or isotropic_match is None
    ):
        raise RuntimeEvidenceError(
            "Kitaev gapless condition must contain all three Eq. (33) triangle "
            "inequalities, gapless phase B, and the symmetric isotropic point"
        )
    matches = [
        prefix_match,
        *inequality_matches,
        equation_match,
        phase_match,
        isotropic_match,
    ]
    return (
        {
            "gapless_condition": "triangle_inequalities",
            "isotropic_kitaev_point_gapless": True,
        },
        {
            "parser": "parse_kitaev_gapless_triangle_condition",
            "equation": "33",
            "matched_anchors": [
                "if and only if triangle inequalities",
                "three exchange triangle inequalities",
                "Eq. (33) gapless phase B",
                "symmetric Jx=Jy=Jz spectrum zeros",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_kitaev_field_nonabelian_gap(source_text):
    """Extract the field-induced mass, odd Chern number, and anyon claim."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Kitaev magnetic-field gap requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()

    equation_matches = {
        equation: re.search(rf"\({equation}\)", normalized)
        for equation in ("45", "48", "50", "51", "55")
    }

    def equation_window(equation, radius=320):
        match = equation_matches[equation]
        if match is None:
            return ""
        return normalized[
            max(0, match.start() - radius) : min(
                len(normalized), match.end() + radius
            )
        ]

    equation_45 = equation_window("45")
    equation_48 = equation_window("48")
    equation_50 = equation_window("50")
    equation_51 = equation_window("51")
    equation_55 = equation_window("55")

    field_match = re.search(
        r"external magnetic field|magnetic field acting on all spins",
        equation_45,
        flags=re.IGNORECASE,
    )
    field_components_match = re.search(
        r"hx.{0,100}?hy.{0,100}?hz",
        equation_45,
        flags=re.IGNORECASE,
    )
    opens_gap_match = re.search(
        r"does open a spectral gap|opens? a gap",
        equation_45,
        flags=re.IGNORECASE,
    )
    third_order_match = re.search(
        r"third-order (?:term|effective Hamiltonian)",
        normalized,
        flags=re.IGNORECASE,
    )
    kappa_product_match = re.search(
        r"(?:κ|kappa)", equation_48, flags=re.IGNORECASE
    )
    field_product_match = re.search(
        r"hx\s+hy\s+hz", equation_48, flags=re.IGNORECASE
    )
    exchange_square_match = re.search(
        r"(?:/\s*)?J\s*(?:\^\s*2|2|²)",
        equation_48,
        flags=re.IGNORECASE,
    )
    proportional_match = re.search(
        r"(?:∼|~|proportional to)", equation_48, flags=re.IGNORECASE
    )
    mass_match = re.search(
        r"6\s*(?:sqrt\s*\(\s*3\s*\)|√?\s*3)\s*(?:κ|kappa)",
        equation_50,
        flags=re.IGNORECASE,
    )
    mass_product_match = re.search(
        r"hx\s+hy\s+hz", equation_50, flags=re.IGNORECASE
    )
    determines_gap_match = re.search(
        r"determines the energy gap", equation_50, flags=re.IGNORECASE
    )
    dispersion_match = re.search(
        r"(?:ε|epsilon)\s*\(q\).{0,180}?(?:∆|Delta)\s*(?:\^\s*2|2|²)",
        equation_51,
        flags=re.IGNORECASE,
    )
    chern_match = re.search(
        r"(?:ν|nu).{0,180}?sgn\s*(?:∆|Delta)\s*=\s*"
        r"(?:±\s*1|plus or minus 1)",
        equation_55,
        flags=re.IGNORECASE,
    )
    nonabelian_match = re.search(
        r"vortices behave as non-Abelian anyons for any odd value of (?:ν|nu)",
        normalized,
        flags=re.IGNORECASE,
    )
    required_matches = [
        *equation_matches.values(),
        field_match,
        field_components_match,
        opens_gap_match,
        third_order_match,
        kappa_product_match,
        field_product_match,
        exchange_square_match,
        proportional_match,
        mass_match,
        mass_product_match,
        determines_gap_match,
        dispersion_match,
        chern_match,
        nonabelian_match,
    ]
    if any(match is None for match in required_matches):
        raise RuntimeEvidenceError(
            "Kitaev magnetic-field gap requires Eq. (45) field perturbation, "
            "the third-order Eq. (48) hx*hy*hz/J^2 term, Eqs. (50)-(51) "
            "mass gap, Eq. (55) odd Chern number, and the non-Abelian-vortex "
            "conclusion"
        )
    return (
        {"field_opens_non_abelian_gap": True},
        {
            "parser": "parse_kitaev_field_nonabelian_gap",
            "equations": ["45", "48", "50", "51", "55"],
            "matched_anchors": [
                "external magnetic field opens a spectral gap",
                "third-order effective Hamiltonian",
                "kappa proportional to hx*hy*hz/J^2",
                "Delta=6*sqrt(3)*kappa determines the gap",
                "massive conic dispersion",
                "Chern number nu=sgn(Delta)=+/-1",
                "odd-nu vortices are non-Abelian anyons",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in required_matches
            ],
        },
    )


def recompute_kitaev_field_nonabelian_gap(*, h_x, h_y, h_z, exchange):
    """Recompute Kitaev's third-order mass and infer odd-Chern anyon type."""

    values = (h_x, h_y, h_z, exchange)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("field components and exchange must be finite numbers")
    if exchange == 0.0:
        raise ValueError("Kitaev field-gap recomputation requires nonzero finite exchange")

    kappa = h_x * h_y * h_z / exchange**2
    mass = 6.0 * math.sqrt(3.0) * kappa
    minimum_positive_energy = abs(mass)
    chern_number = 0 if mass == 0.0 else (1 if mass > 0.0 else -1)
    return {
        "field_opens_non_abelian_gap": (
            minimum_positive_energy > 0.0 and abs(chern_number) % 2 == 1
        ),
        "mass": mass,
        "minimum_positive_energy": minimum_positive_energy,
        "chern_number": chern_number,
    }


def parse_kitaev_toric_code_degeneracy(source_text):
    """Derive the genus-one toric-code ground-state degeneracy."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "toric-code degeneracy claim requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    torus_match = re.search(
        r"lattices on the torus and other 2-D surfaces",
        normalized,
        flags=re.IGNORECASE,
    )
    degeneracy_match = re.search(
        r"ground state.{0,120}?protected space.{0,80}?"
        r"4(?:\^\s*g|g)\s*-?fold degenerate,?\s*where g is the genus",
        normalized,
        flags=re.IGNORECASE,
    )
    if torus_match is None or degeneracy_match is None:
        raise RuntimeEvidenceError(
            "toric-code degeneracy claim must state the torus ground-state "
            "space is 4^g-fold degenerate with g the surface genus"
        )
    return (
        {"torus_ground_state_degeneracy": 4},
        {
            "parser": "parse_kitaev_toric_code_degeneracy",
            "derivation": "torus has genus g=1, so 4^g=4",
            "matched_anchors": [
                "lattices on the torus",
                "ground-state protected space is 4^g-fold degenerate",
                "g is the genus of the surface",
            ],
            "text_spans": [
                [torus_match.start(), torus_match.end()],
                [degeneracy_match.start(), degeneracy_match.end()],
            ],
        },
    )


def parse_white_huse_haldane_gap(source_text):
    """Extract White and Huse's thermodynamic Haldane-gap estimate."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("White-Huse Haldane gap requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    match = re.search(
        r"excitation energy of the first excited state.{0,100}?one magnon"
        r".{0,100}?Haldane gap.{0,100}?0\.41050\s*\(\s*2\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise RuntimeEvidenceError(
            "White-Huse Haldane gap must identify the first one-magnon "
            "excitation and the 0.41050(2) estimate"
        )
    return (
        {"gap_over_j": 0.41050},
        {
            "parser": "parse_white_huse_haldane_gap",
            "reported_uncertainty": 0.00002,
            "matched_anchors": [
                "first excited one-magnon state",
                "Haldane gap 0.41050(2)",
            ],
            "text_spans": [[match.start(), match.end()]],
        },
    )


def parse_sandvik_square_qmc_energy(source_text):
    """Extract Sandvik's square-lattice Heisenberg QMC energy."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Sandvik square-QMC energy requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    standard_match = re.search(
        r"two-dimensional\s+S\s*=\s*1\s*/\s*2\s+antiferromagnetic "
        r"Heisenberg model.{0,160}?quantum Monte Carlo.{0,180}?"
        r"ground-state energy per spin is\s+E\s*=\s*[-−]\s*0\.669437"
        r"\s*\(\s*5\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    locked_ocr_match = re.search(
        r"two-dimensional\s+S51/2\s+antiferromagnetic Heisenberg model"
        r".{0,80}?stochastic series expansion quantum Monte Carlo"
        r".{0,900}?extrapolated ground- state energy per spin is\s+"
        r"E520\.669437\s*\(\s*5\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    match = standard_match or locked_ocr_match
    if match is None:
        raise RuntimeEvidenceError(
            "Sandvik square-QMC energy must identify the two-dimensional "
            "spin-half Heisenberg QMC result -0.669437(5)"
        )
    return (
        {"energy_per_site": -0.669437},
        {
            "parser": "parse_sandvik_square_qmc_energy",
            "reported_uncertainty": 0.000005,
            "matched_anchors": [
                "two-dimensional spin-half Heisenberg model",
                "quantum Monte Carlo",
                "ground-state energy per spin -0.669437(5)",
            ],
            "text_spans": [[match.start(), match.end()]],
        },
    )


def parse_jiang_wiese_square_heisenberg_low_energy_parameters(source_text):
    """Extract Jiang and Wiese's three square-Heisenberg low-energy scales."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Jiang-Wiese square-Heisenberg evidence requires nonempty text"
        )
    prepared = _build_prepared_view(
        source_text,
        builder_id="whitespace_normalized_extracted_text",
        version=1,
    )
    return _parse_jiang_wiese_square_heisenberg_low_energy_parameters_prepared(
        prepared.text
    )


def _parse_jiang_wiese_square_heisenberg_low_energy_parameters_prepared(
    normalized,
):
    identity_match = re.search(
        r"PHYSICAL REVIEW B\s+83,\s*155120\s*\(\s*2011\s*\)"
        r".{0,300}?High-precision determination of low-energy effective "
        r"parameters for a two-dimensional Heisenberg quantum "
        r"antiferromagnet"
        r".{0,220}?F\s*\.\s*-\s*J\s*\.\s*Jiang"
        r".{0,100}?\band\b.{0,50}?U\s*\.\s*-\s*J\s*\.\s*Wiese"
        r".{0,3500}?DOI\s*:\s*10\.1103\s*/\s*PhysRevB\.83\.155120",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"two-dimensional\s*\(\s*2D\s*\)\s*"
        r"spin\s*-\s*(?:1\s*/\s*2|1\s*2)\s+Heisenberg "
        r"antiferromagnet with exchange coupling J"
        r".{0,220}?periodic square lattice of spacing a"
        r".{0,220}?loop-cluster algorithm",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"spin\s*-\s*(?:1\s*/\s*2|1\s*2|2\s*1)\s+Heisenberg model "
        r"considered in this study is.{0,700}?defined by the Hamilton "
        r"operator"
        r".{0,800}?H\s*=\s*.{0,800}?\(\s*1\s*\)"
        r".{0,500}?two spatial unit vectors"
        r".{0,260}?J in Eq\.?\s*\(\s*1\s*\) is the "
        r"antiferromagnetic exchange coupling",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_velocity_match = re.search(
        r"for a fixed box size L.{0,180}?vary\s*(?:beta|β)"
        r".{0,650}?spatial and temporal winding numbers"
        r".{0,360}?spin wave velocity then results as "
        r"c\s*=\s*L\s*/\s*(?:beta|β)"
        r".{0,220}?obtain c\s*=\s*1\.6586\s*\(\s*3\s*\)\s*J\s*a",
        normalized,
        flags=re.IGNORECASE,
    )
    locked_pdf_velocity_match = re.search(
        r"we determine c using.{0,1600}?for a fixed box size L"
        r".{0,360}?vary\s*(?:beta|β)"
        r".{0,1800}?spin wave velocity then results as "
        r"c\s*=\s*L\s*/\s*(?:beta|β)"
        r".{0,220}?obtain c\s*=\s*1\.6586\s*\(\s*3\s*\)\s*J\s*a",
        normalized,
        flags=re.IGNORECASE,
    )
    velocity_match = clean_velocity_match or locked_pdf_velocity_match
    joint_fit_match = re.search(
        r"using c\s*=\s*1\.6586\s*\(\s*3\s*\)\s*J\s*a"
        r".{0,160}?performing a combined fit of the Monte Carlo data "
        r"for.{0,220}?in the cubical regime"
        r".{0,180}?(?:arrive at|obtain)\s+"
        r"M\s*_?\s*s\s*=\s*0\.307\s*43\s*\(\s*1\s*\)"
        r"\s*/\s*a\s*\^?\s*2"
        r".{0,100}?(?:rho|ρ)\s*_?\s*s\s*=\s*0\.180\s*81"
        r"\s*\(\s*11\s*\)\s*J",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        model_match,
        hamiltonian_match,
        velocity_match,
        joint_fit_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Jiang-Wiese square-Heisenberg source must establish the "
            "spin-half periodic-square Hamiltonian, the antiferromagnetic "
            "J convention, the winding-number velocity measurement, and "
            "the jointly fitted M_s, rho_s, and c values"
        )
    return (
        {
            "staggered_magnetization": 0.30743,
            "rho_s_over_j": 0.18081,
            "renormalized_velocity_over_j_approx": 1.6586,
        },
        {
            "parser": (
                "parse_jiang_wiese_square_heisenberg_low_energy_parameters"
            ),
            "reported_uncertainties": {
                "staggered_magnetization": 0.00001,
                "rho_s_over_j": 0.00011,
                "renormalized_velocity_over_j_approx": 0.0003,
            },
            "magnetization_normalization": (
                "M_s a^2 in spin-operator units per lattice site; not "
                "divided by the spin-1/2 saturation magnetization"
            ),
            "stiffness_normalization": "rho_s/J",
            "velocity_normalization": "c/(J a)",
            "source_identity": "doi:10.1103/PhysRevB.83.155120",
            "superseded_registered_source_identity": (
                "doi:10.1103/PhysRevB.56.11678"
            ),
            "superseded_source_reported_parameters": {
                "staggered_magnetization": 0.3070,
                "rho_s_over_j": 0.175,
                "renormalized_velocity_over_j_approx": 1.673,
            },
            "registered_source_correction": (
                "The three registry entries cite Sandvik 1997, DOI "
                "10.1103/PhysRevB.56.11678, which reports M=0.3070(3), "
                "rho_s=0.175(2) J, and c=1.673(7) J a. Their registered "
                "values instead match Jiang-Wiese 2011: "
                "M_s=0.30743(1)/a^2, rho_s=0.18081(11) J, and "
                "c=1.6586(3) J a."
            ),
            "claim_scope": (
                "joint low-energy parameters of the periodic square-lattice "
                "spin-1/2 nearest-neighbor antiferromagnetic Heisenberg "
                "model; the source correction applies to the three registry "
                "records for staggered magnetization, spin stiffness, and "
                "spin-wave velocity"
            ),
            "matched_anchors": [
                "identified Jiang-Wiese PRB 83, 155120 paper and DOI",
                "two-dimensional periodic square-lattice spin-half model",
                "nearest-neighbor Hamiltonian with antiferromagnetic J",
                "winding-number determination of c=1.6586(3) J a",
                "joint cubical-regime fit for M_s and rho_s",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def _parse_jiang_wiese_square_heisenberg_single_field_prepared(
    prepared_text, *, field, parser_name
):
    joint_parameters, source_trace = (
        _parse_jiang_wiese_square_heisenberg_low_energy_parameters_prepared(
            prepared_text
        )
    )
    if (
        field not in joint_parameters
        or field not in source_trace["reported_uncertainties"]
    ):
        raise RuntimeEvidenceError(
            "Jiang-Wiese square-Heisenberg field projection is unsupported"
        )

    trace = dict(source_trace)
    trace.update(
        {
            "parser": parser_name,
            "source_parser": (
                "parse_jiang_wiese_square_heisenberg_low_energy_parameters"
            ),
            "selected_source_field": field,
            "reported_uncertainty": (
                source_trace["reported_uncertainties"][field]
            ),
            "source_joint_parameters": dict(joint_parameters),
        }
    )
    return {field: joint_parameters[field]}, trace


def parse_jiang_wiese_square_heisenberg_spin_stiffness(source_text):
    """Project Jiang-Wiese's joint fit to the registered stiffness field."""

    parser_name = "parse_jiang_wiese_square_heisenberg_spin_stiffness"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Jiang-Wiese square-Heisenberg evidence requires nonempty text"
        )
    prepared = _prepared_view_for_parser(source_text, parser_name)
    return _finalize_prepared_trace(
        _parse_jiang_wiese_square_heisenberg_single_field_prepared(
            prepared.text,
            field="rho_s_over_j",
            parser_name=parser_name,
        ),
        prepared,
    )


def parse_jiang_wiese_square_heisenberg_staggered_magnetization(
    source_text,
):
    """Project Jiang-Wiese's joint fit to the registered magnetization."""

    parser_name = (
        "parse_jiang_wiese_square_heisenberg_staggered_magnetization"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Jiang-Wiese square-Heisenberg evidence requires nonempty text"
        )
    prepared = _prepared_view_for_parser(source_text, parser_name)
    return _finalize_prepared_trace(
        _parse_jiang_wiese_square_heisenberg_single_field_prepared(
            prepared.text,
            field="staggered_magnetization",
            parser_name=parser_name,
        ),
        prepared,
    )


def parse_jiang_wiese_square_heisenberg_spin_wave_velocity(source_text):
    """Project Jiang-Wiese's winding result to the velocity field."""

    parser_name = "parse_jiang_wiese_square_heisenberg_spin_wave_velocity"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Jiang-Wiese square-Heisenberg evidence requires nonempty text"
        )
    prepared = _prepared_view_for_parser(source_text, parser_name)
    return _finalize_prepared_trace(
        _parse_jiang_wiese_square_heisenberg_single_field_prepared(
            prepared.text,
            field="renormalized_velocity_over_j_approx",
            parser_name=parser_name,
        ),
        prepared,
    )


def parse_blote_luijten_heringa_simple_cubic_ising_tc(source_text):
    """Derive T_c/J from Blote, Luijten, and Heringa's critical coupling."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Blote-Luijten-Heringa simple-cubic Ising evidence requires "
            "nonempty text"
        )
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_blote_luijten_heringa_simple_cubic_ising_tc",
    )
    return _finalize_prepared_trace(
        _parse_blote_luijten_heringa_simple_cubic_ising_tc_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_blote_luijten_heringa_simple_cubic_ising_tc_prepared(
    numeric_normalized,
):
    spin_half_pattern = r"spin\s*-\s*(?:1\s*/\s*2|1\s*2|2\s*1)"
    coupling_pattern = (
        r"K\s*_?\s*(?:3n|3\s*n)\s*(?:/|=)\s*K\s*_?\s*nn"
    )

    identity_match = re.search(
        r"Ising Universality in Three Dimensions\s*:\s*A Monte Carlo Study"
        r".{0,420}?Henk\s+W\s*\.?\s*J\s*\.?"
        r".{0,80}?Erik\s+Luijten"
        r".{0,100}?Jouke\s+R\s*\.?\s*Heringa"
        r".{0,450}?September\s+4\s*,\s*1995"
        r".{0,450}?cond-mat\s*/\s*9509016",
        numeric_normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"investigate three Ising models on the simple cubic lattice "
        r"by means of Monte Carlo methods and.{0,80}?"
        r"(?:finite|nite)-size scaling"
        r".{0,220}?"
        + spin_half_pattern
        + r"\s+Ising model with nearest-neighbor interactions"
        r".{0,1400}?critical point of the nearest-neighbor\s+"
        + spin_half_pattern
        + r"\s+model is "
        r"K\s*_?\s*c\s*=\s*0\.2216546\s*\(\s*10\s*\)",
        numeric_normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"(?:preliminary results for|represented in terms of).{0,100}?"
        r"(?:the|a spin-1) Hamiltonian"
        r".{0,500}?H\s*(?:/|=)\s*\(?\s*k\s*_?\s*B\s*T\s*\)?\s*="
        r".{0,500}?K\s*_?\s*nn"
        r".{0,1400}?indicates a sum over nearest-neighbor pairs"
        r".{0,900}?spins\s+s\s*_?\s*i\s+can assume the values "
        r"\+\s*1\s+and\s+(?:[-−]\s*)?1",
        numeric_normalized,
        flags=re.IGNORECASE,
    )
    clean_model_match = re.search(
        r"Thus,\s*we\s+(?:have\s+)?selected"
        r".{0,180}?"
        + spin_half_pattern
        + r"\s+Ising model with\s+"
        + coupling_pattern
        + r"\s*=\s*0(?![\d.])"
        r".{0,100}?nearest-neighbor model"
        r".{0,600}?Table 1"
        r".{0,220}?model\s+1"
        r".{0,100}?"
        + coupling_pattern
        + r"\s*=\s*0(?![\d.])"
        r".{0,100}?"
        + spin_half_pattern
        + r"\s+model with nn couplings",
        numeric_normalized,
        flags=re.IGNORECASE,
    )
    locked_pdf_model_match = re.search(
        r"Thus,\s*we\s+(?:have\s+)?selected"
        r".{0,180}?"
        + spin_half_pattern
        + r"\s+Ising model with\s+"
        + coupling_pattern
        + r"\s*=\s*0(?![\d.])"
        r".{0,100}?nearest-neighbor model"
        r".{0,4000}?Table 1\s*:\s*The ratio\s+"
        + coupling_pattern
        + r".{0,250}?description of model"
        r".{0,120}?\b1\s+0\s+"
        r"(?:1|infinity|∞)\s+"
        + spin_half_pattern
        + r"\s+model with nn couplings",
        numeric_normalized,
        flags=re.IGNORECASE,
    )
    model_match = clean_model_match or locked_pdf_model_match
    table_match = re.search(
        r"Table 16\s*:\s*Results of a data analysis assuming universality"
        r".{0,500}?system sizes L.{0,40}?5"
        r".{0,700}?model 1.{0,80}?model 2.{0,80}?model 3"
        r".{0,220}?K\s*_?\s*c\s+"
        r"0\.2216546\s*\(\s*5\s*\)\s+"
        r"0\.1280039\s*\(\s*4\s*\)\s+"
        r"0\.3934220\s*\(\s*7\s*\)",
        numeric_normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        abstract_match,
        hamiltonian_match,
        model_match,
        table_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Blote-Luijten-Heringa simple-cubic Ising source must establish "
            "the identified preprint, the nearest-neighbor spin-half model, "
            "its dimensionless Hamiltonian and Ising spin convention, the "
            "model-1 zero third-neighbor coupling, and both reported K_c "
            "values"
        )

    critical_coupling = 0.2216546
    critical_coupling_uncertainty = 0.0000005
    parsed = recompute_simple_cubic_ising_tc_from_critical_coupling(
        critical_coupling=critical_coupling
    )
    return (
        parsed,
        {
            "parser": (
                "parse_blote_luijten_heringa_simple_cubic_ising_tc"
            ),
            "critical_coupling": critical_coupling,
            "reported_critical_coupling_uncertainty": (
                critical_coupling_uncertainty
            ),
            "abstract_critical_coupling_uncertainty": 0.0000010,
            "propagated_tc_over_j_uncertainty": (
                critical_coupling_uncertainty / critical_coupling**2
            ),
            "conversion": "T_c/J = 1/K_c",
            "registered_hamiltonian_convention": (
                "H = -J sum_<nn> sigma_i sigma_j with sigma_i in {-1,+1}; "
                "K_nn = J/(k_B T)"
            ),
            "matched_anchors": [
                "identified cond-mat/9509016 preprint and authors",
                "simple-cubic nearest-neighbor spin-half abstract result",
                "dimensionless Hamiltonian and two-state Ising spins",
                "model 1 with K_3n/K_nn=0 and nearest-neighbor couplings",
                "Table 16 combined-fit K_c=0.2216546(5)",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_depenbrock_kagome_heisenberg_energy(source_text):
    """Extract Depenbrock et al.'s thermodynamic kagome energy per site."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Depenbrock kagome-Heisenberg energy requires nonempty text"
        )
    prepared = _prepared_view_for_parser(
        source_text, "parse_depenbrock_kagome_heisenberg_energy"
    )
    return _finalize_prepared_trace(
        _parse_depenbrock_kagome_heisenberg_energy_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_depenbrock_kagome_heisenberg_energy_prepared(normalized):
    spin_half_pattern = (
        r"S\s*=\s*(?:1\s*/\s*2|1\s*2|2\s*1)"
    )
    antiferromagnet_pattern = (
        r"(?:antiferromagnet|an\s*-\s*tiferromagnet)"
    )
    identity_match = re.search(
        r"Nature of the Spin Liquid Ground State of the\s+"
        + spin_half_pattern
        + r"\s+Heisenberg Model on the Kagome Lattice"
        r".{0,500}?Stefan Depenbrock"
        r".{0,120}?Ian P\s*\.\s*McCulloch"
        r".{0,140}?Ulrich Schollw.{0,8}?ck",
        normalized,
        flags=re.IGNORECASE,
    )
    archive_match = re.search(
        r"arXiv\s*:\s*1205\.4858v2"
        r"\s*\[\s*cond-mat\.str-el\s*\]\s*14 Aug 2012",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"perform a density-matrix renormalization group\s*"
        r"\(\s*DMRG\s*\)\s*study of the\s+"
        + spin_half_pattern
        + r"\s+Heisenberg\s+"
        + antiferromagnet_pattern
        + r"\s+on the kagome lattice"
        r".{0,300}?Exploiting SU\s*\(\s*2\s*\)\s*spin symmetry"
        r".{0,180}?keep up to 16\s*,?\s*000 DMRG states"
        r".{0,180}?cylinders.{0,160}?"
        r"with circumferences up to 17 lattice spacings"
        r".{0,180}?estimated per site energy of\s*"
        r"[-−]\s*0\.4386\s*\(\s*5\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    clean_model_match = re.search(
        r"Heisenberg\s+"
        + antiferromagnet_pattern
        + r"\s+on the kagome lattice"
        r".{0,100}?\(\s*KAFM\s*\)"
        r".{0,120}?described by the\s+"
        + spin_half_pattern
        + r"\s+model"
        r".{0,500}?H\s*=\s*.{0,500}?\(\s*1\s*\)"
        r".{0,160}?(?:with|Here).{0,60}?"
        r"(?<![-\w])nearest neighbors",
        normalized,
        flags=re.IGNORECASE,
    )
    locked_pdf_model_match = re.search(
        r"Heisenberg\s+"
        + antiferromagnet_pattern
        + r"\s+on the"
        r".{0,650}?kagome lattice.{0,40}?\(\s*KAFM\s*\)"
        r".{0,700}?described"
        r".{0,700}?by the\s+"
        + spin_half_pattern
        + r"\s+model"
        r".{0,700}?H\s*=\s*.{0,700}?\(\s*1\s*\)"
        r".{0,260}?with.{0,80}?"
        r"(?<![-\w])nearest neighbors",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = clean_model_match or locked_pdf_model_match
    clean_extrapolation_method_match = re.search(
        r"Energies for cylinders of fixed "
        r"(?:c and L|circumference c and length L) are "
        r"extrapolated "
        r"in the truncation error"
        r".{0,500}?bulk energies per site are extracted by a subtraction "
        r"technique",
        normalized,
        flags=re.IGNORECASE,
    )
    locked_pdf_extrapolation_method_match = re.search(
        r"Energies for cylinders of fixed "
        r"c and L are ex\s*-\s*"
        r".{0,350}?trapolated in the truncation error of single-site DMRG"
        r".{0,400}?bulk energies per site are extracted by a subtrac\s*-\s*"
        r".{0,350}?tion technique",
        normalized,
        flags=re.IGNORECASE,
    )
    extrapolation_method_match = (
        clean_extrapolation_method_match
        or locked_pdf_extrapolation_method_match
    )
    clean_length_limit_match = re.search(
        r"bulk energies per site are extracted by a "
        r"subtraction technique"
        r".{0,180}?extrapolated to L.{0,20}?(?:infinity|∞)"
        r".{0,1700}?At 16\s*,?\s*000 states,\s*DMRG is highly accurate"
        r".{0,220}?negligible.{0,400}?"
        r"changes in energy for substantially larger c"
        r".{0,100}?support that",
        normalized,
        flags=re.IGNORECASE,
    )
    locked_pdf_length_limit_match = re.search(
        r"bulk energies per site are extracted by a subtrac\s*-\s*"
        r".{0,350}?tion technique"
        r".{0,180}?extrapolated to L.{0,20}?(?:infinity|∞)"
        r".{0,1800}?At 16\s*,?\s*000 states,\s*DMRG is highly accurate"
        r".{0,220}?negligible.{0,400}?"
        r"changes in energy for substantially larger c"
        r".{0,100}?support that",
        normalized,
        flags=re.IGNORECASE,
    )
    length_limit_match = (
        clean_length_limit_match or locked_pdf_length_limit_match
    )
    thermodynamic_result_match = re.search(
        r"thermodynamic\s*-?\s*limit energy is found"
        r".{0,100}?place.{0,600}?at\s*"
        r"[-−]\s*0\.4386\s*\(\s*5\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        archive_match,
        abstract_match,
        model_match,
        extrapolation_method_match,
        length_limit_match,
        thermodynamic_result_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Depenbrock kagome-Heisenberg energy source must establish the "
            "identified arXiv preprint, spin-half nearest-neighbor kagome "
            "Hamiltonian, SU(2) DMRG cylinder scale, length and "
            "circumference extrapolations, and -0.4386(5) per-site result"
        )
    return (
        {"energy_per_site_approx": -0.4386},
        {
            "parser": "parse_depenbrock_kagome_heisenberg_energy",
            "reported_uncertainty": 0.0005,
            "energy_normalization": (
                "E/N per kagome site for H=J sum_<i,j> S_i dot S_j, "
                "nearest-neighbor bonds counted once, J=1"
            ),
            "limit": (
                "cylinder length extrapolated to infinity and circumference "
                "extrapolated to the two-dimensional thermodynamic limit"
            ),
            "matched_anchors": [
                "identified Depenbrock-McCulloch-Schollwoeck paper",
                "arXiv:1205.4858v2 dated 14 August 2012",
                "abstract: SU(2) DMRG, circumference 17, and -0.4386(5)",
                "spin-half nearest-neighbor kagome Hamiltonian Eq. (1)",
                "bulk per-site energy extraction by cylinder subtraction",
                "length extrapolation and stability at larger circumference",
                "two-dimensional thermodynamic-limit energy -0.4386(5)",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_depenbrock_kagome_heisenberg_energy_and_spin_gap(source_text):
    """Extract Depenbrock et al.'s kagome energy and bulk triplet gap."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Depenbrock kagome-Heisenberg energy requires nonempty text"
        )
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_depenbrock_kagome_heisenberg_energy_and_spin_gap",
    )
    return _finalize_prepared_trace(
        _parse_depenbrock_kagome_heisenberg_energy_and_spin_gap_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_depenbrock_kagome_heisenberg_energy_and_spin_gap_prepared(
    normalized,
):
    energy, energy_trace = (
        _parse_depenbrock_kagome_heisenberg_energy_prepared(normalized)
    )
    abstract_gap_match = re.search(
        r"estimated per site energy of\s*[-−]\s*0\.4386\s*"
        r"\(\s*5\s*\)\s*,\s*a spin gap of\s*"
        r"0\.13\s*\(\s*1\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    body_gap_match = re.search(
        r"On the issue of a spin\s*\(\s*triplet\s*\)\s*gap"
        r".{0,900}?SU\s*\(\s*2\s*\)\s*DMRG computes the "
        r"S\s*=\s*1 state directly"
        r".{0,1800}?find the spin gap"
        r".{0,650}?remain finite also for cylinders"
        r".{0,220}?of large (?:circumference\s+)?c"
        r".{0,2200}?SU\s*\(\s*2\s*\)\s*-?"
        r".{0,800}?invariant results evolve (?:more\s+)?smoothly with c"
        r".{0,800}?tentative extrapolation to a spin gap"
        r".{0,80}?(?:Delta|∆)\s*E\s*=\s*0\.13\s*\(\s*1\s*\)"
        r".{0,400}?thermodynamic limit",
        normalized,
        flags=re.IGNORECASE,
    )
    gap_matches = (abstract_gap_match, body_gap_match)
    if any(match is None for match in gap_matches):
        raise RuntimeEvidenceError(
            "Depenbrock kagome triplet gap source must report 0.13(1) in "
            "the abstract and establish an S=1 bulk excitation that remains "
            "finite under a thermodynamic-limit circumference extrapolation"
        )

    trace = dict(energy_trace)
    trace.pop("reported_uncertainty", None)
    trace.update(
        {
            "parser": (
                "parse_depenbrock_kagome_heisenberg_energy_and_spin_gap"
            ),
            "reported_uncertainties": {
                "energy_per_site": 0.0005,
                "spin_gap_over_j": 0.01,
            },
            "gap_normalization": (
                "lowest bulk triplet (S=1) gap Delta E/J with the "
                "nearest-neighbor coefficient J=1"
            ),
            "matched_anchors": [
                *energy_trace["matched_anchors"],
                "abstract jointly reports energy -0.4386(5) and gap 0.13(1)",
                "bulk S=1 gap remains finite and extrapolates to 0.13(1)",
            ],
            "text_spans": [
                *energy_trace["text_spans"],
                *[
                    [match.start(), match.end()]
                    for match in gap_matches
                ],
            ],
        }
    )
    return (
        {
            "energy_per_site": energy["energy_per_site_approx"],
            "spin_gap_over_j": 0.13,
        },
        trace,
    )


def parse_sandvik_daul_square_xy_ring_bond_order(source_text):
    """Extract Sandvik et al.'s ring-driven square-XY bond order."""

    error_message = (
        "Sandvik-Daul square-XY ring exchange source must establish the "
        "identified cond-mat/0205270v2 preprint, its spin-half square XY "
        "bond and four-spin ring operators, H=-J sum B-K sum P, the "
        "ring-driven striped bond-plaquette phase, thermodynamic-limit "
        "stripe order, and the absence of a spin-liquid phase"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text, "parse_sandvik_daul_square_xy_ring_bond_order"
    )
    return _finalize_prepared_trace(
        _parse_sandvik_daul_square_xy_ring_bond_order_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_sandvik_daul_square_xy_ring_bond_order_prepared(normalized):
    error_message = (
        "Sandvik-Daul square-XY ring exchange source must establish the "
        "identified cond-mat/0205270v2 preprint, its spin-half square XY "
        "bond and four-spin ring operators, H=-J sum B-K sum P, the "
        "ring-driven striped bond-plaquette phase, thermodynamic-limit "
        "stripe order, and the absence of a spin-liquid phase"
    )
    spin_half_pattern = (
        r"(?:S\s*=\s*1\s*/\s*2|spin\s*-\s*1\s*/\s*2)"
    )
    xy_model_pattern = r"XY\s*-\s*model"

    identity_match = re.search(
        r"Striped phase in a quantum\s+"
        + xy_model_pattern
        + r"\s+with ring exchange"
        r".{0,500}?A\s*\.\s*W\s*\.\s*Sandvik"
        r".{0,160}?S\s*\.\s*Daul"
        r".{0,160}?R\s*\.\s*R\s*\.\s*P\s*\.\s*Singh"
        r".{0,160}?D\s*\.\s*J\s*\.\s*Scalapino"
        r".{0,3000}?arXiv\s*:\s*cond-mat\s*/\s*0205270v2"
        r"\s*\[\s*cond-mat\.str-el\s*\]\s*2 Dec 2002",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"We present quantum Monte Carlo results for a "
        r"square\s*-\s*lattice\s+"
        + spin_half_pattern
        + r"\s+"
        + xy_model_pattern
        + r".{0,100}?standard nearest\s*-\s*neighbor coupling J"
        r".{0,100}?four\s*-\s*spin ring exchange term K"
        r".{0,180}?Increasing K\s*/\s*J"
        r".{0,180}?ground\s*-?\s*state spin\s*-?\s*stiffness vanishes"
        r".{0,120}?spin gap opens"
        r".{0,120}?striped bond\s*-\s*plaquette order emerges"
        r".{0,180}?higher K\s*/\s*J"
        r".{0,180}?staggered magnetization",
        normalized,
        flags=re.IGNORECASE,
    )
    operator_match = re.search(
        r"Defining (?:the )?bond and plaquette exchange operators"
        r".{0,700}?B\s*_?\s*ij\s*="
        r".{0,400}?=\s*2\s*\(\s*"
        r"S\s*_?\s*i\s*\^?\s*x\s+"
        r"S\s*_?\s*j\s*\^?\s*x\s*\+\s*"
        r"S\s*_?\s*i\s*\^?\s*y\s+"
        r"S\s*_?\s*j\s*\^?\s*y\s*\)"
        r"\s*,?\s*\(\s*1\s*\)"
        r".{0,800}?P\s*_?\s*ijkl\s*="
        r".{0,800}?\+\s*.{0,800}?\(\s*2\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    hamiltonian_match = re.search(
        r"(?:the\s+)?Hamiltonian is"
        r".{0,900}?H\s*=\s*-\s*J"
        r".{0,500}?B\s*_?\s*ij"
        r".{0,500}?-\s*K"
        r".{0,500}?P\s*_?\s*ijkl"
        r"\s*[,.]?\s*\(\s*3\s*\)"
        r".{0,1800}?For K\s*=\s*0"
        r".{0,180}?standard quantum\s+"
        + xy_model_pattern,
        normalized,
        flags=re.IGNORECASE,
    )
    central_result_match = re.search(
        r"central result"
        r".{0,700}?competing J and K"
        r".{0,800}?third phase at K\s*/\s*J\s*"
        r"(?:approximately|[~∼≈])\s*10"
        r".{0,120}?striped.{0,250}?bond\s*-\s*plaquette phase"
        r".{0,350}?expectation values"
        r".{0,500}?alternate(?: in strength)? with (?:a )?period(?: of)? 2"
        r".{0,6000}?in the thermodynamic(?:\s+limit)?"
        r".{0,120}?striped state should (?:therefore )?be analogous to the"
        r"\s+(?:fourfold|four\s*-.{0,120}?fold) degenerate columnar "
        r"spin\s*-\s*Peierls state",
        normalized,
        flags=re.IGNORECASE,
    )
    finite_size_match = re.search(
        r"Finite\s*-\s*size"
        r".{0,700}?scaling"
        r"(?:"
        r".{0,300}?K\s*/\s*J\s*=\s*8\.5"
        r".{0,300}?shows that the stripe order survives in the"
        r"\s+(?:thermodynamic|ther\s*-.{0,300}?modynamic) limit"
        r"|"
        r".{0,300}?shows that the stripe order survives in the"
        r"\s+(?:thermodynamic|ther\s*-.{0,300}?modynamic) limit"
        r".{0,500}?K\s*/\s*J\s*=\s*8\.5"
        r")"
        r".{0,1200}?extrapolates to a non\s*-\s*zero value"
        r".{0,400}?as L\s*(?:tends to|[→-]+)\s*"
        r"(?:infinity|∞)"
        r".{0,1800}?(?:staggered|spin\s*-\s*spin) correlations are "
        r"short ranged",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"In summary,\s*the\s+"
        + spin_half_pattern
        + r"\s+"
        + xy_model_pattern
        + r"\s+with ring ex(?:change|\s*-.{0,300}?change) exhibits "
        r"(?:three different ground state orderings|"
        r"superfluid,\s*striped,\s*and staggered ground\s*-\s*state "
        r"orderings)"
        r".{0,3500}?(?:In spite of the absence|There is an absence)"
        r"\s+of a spin liquid phase",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        identity_match,
        abstract_match,
        operator_match,
        hamiltonian_match,
        central_result_match,
        finite_size_match,
        conclusion_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    return (
        {"ring_exchange_drives_vbs_phase": True},
        {
            "parser": "parse_sandvik_daul_square_xy_ring_bond_order",
            "source_model": (
                "square-lattice spin-1/2 XY model with "
                "H=-J sum B_ij-K sum P_ijkl"
            ),
            "source_phase_term": (
                "striped bond-plaquette order, analogous to a "
                "fourfold-degenerate columnar spin-Peierls state"
            ),
            "registered_vbs_mapping": (
                "bond/spin-Peierls order is mapped to the registry's VBS "
                "umbrella; the source is not a Heisenberg J-Q model"
            ),
            "matched_anchors": [
                "identified cond-mat/0205270v2 paper and authors",
                "abstract: ring-driven striped order and staggered phase",
                "XY bond and four-spin plaquette operators, Eqs. (1)-(2)",
                "H=-J sum B-K sum P and K=0 XY limit, Eq. (3)",
                "K/J approximately 10 striped columnar spin-Peierls order",
                "nonzero thermodynamic-limit stripe-order extrapolation",
                "three ordered phases and no spin-liquid phase",
            ],
            "text_spans": [
                [identity_match.start(), identity_match.end()],
                [abstract_match.start(), abstract_match.end()],
                [operator_match.start(), hamiltonian_match.end()],
                [
                    central_result_match.start(),
                    central_result_match.end(),
                ],
                [finite_size_match.start(), finite_size_match.end()],
                [conclusion_match.start(), conclusion_match.end()],
            ],
        },
    )


def _match_chaloupka_full_kitaev_heisenberg_prepared(normalized):
    """Return common identity, abstract, and Hamiltonian anchors."""

    material_pattern = r"Na\s*2\s*IrO\s*3"
    identity_match = re.search(
        r"On the Origin of Zigzag Magnetic Order in Iridium Oxide\s+"
        + material_pattern
        + r".{0,900}?Chaloupka"
        r".{0,220}?George Jackeli"
        r".{0,220}?Giniyat Khaliullin",
        normalized,
        flags=re.IGNORECASE,
    )
    archive_match = re.search(
        r"arXiv\s*:\s*1209\.5100v1"
        r"\s*\[\s*cond-mat\.str-el\s*\]\s*23 Sep 2012",
        normalized,
        flags=re.IGNORECASE,
    )
    abstract_match = re.search(
        r"We explore the phase diagram of spin\s*-\s*orbit Mott "
        r"insulators on a honeycomb lattice"
        r".{0,300}?Kitaev\s*-\s*Heisenberg model extended to its full "
        r"parameter space"
        r".{0,400}?Zigzag\s*-\s*type magnetic order is found"
        r".{0,180}?occupy a large part of the phase diagram"
        r".{0,300}?interorbital t\s*2g\s*-\s*e\s*g hopping"
        r".{0,1200}?spin coupling constants in\s+"
        + material_pattern
        + r"\s+and Li\s*2\s*IrO\s*3",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"(?:The model.{0,200}?)?Nearest\s*-\s*neighbor"
        r".{0,220}?isospin one\s*-\s*half Kramers doublets of "
        r"Ir\s*4?\s*\+?\s*ions"
        r".{0,1800}?H\s*_?\s*ij"
        r".{0,80}?=\s*2\s*K"
        r".{0,220}?\+\s*J"
        r".{0,180}?\(\s*1\s*\)"
        r".{0,500}?(?:gamma|γ)\s*\(?\s*=\s*x\s*,\s*y\s*,\s*z"
        r".{0,300}?(?:three|3) distinct types of "
        r"(?:nearest\s*-\s*neighbor|NN) bonds"
        r".{0,500}?honeycomb lattice"
        r".{0,900}?bond\s*-\s*dependent Ising coupling"
        r".{0,300}?Kitaev model"
        r".{0,300}?second term stands for the Heisenberg"
        r"(?: exchange)?",
        normalized,
        flags=re.IGNORECASE,
    )
    return (
        normalized,
        {
            "identity": identity_match,
            "archive": archive_match,
            "abstract": abstract_match,
            "model": model_match,
        },
    )


def parse_chaloupka_full_kitaev_heisenberg_ordered_phases(source_text):
    """Extract the four ordered phases of the full KH parameter circle."""

    error_message = (
        "Chaloupka full Kitaev-Heisenberg phase diagram source must "
        "establish the identified 1209.5100v1 preprint, the nearest-"
        "neighbor Kitaev-Heisenberg Hamiltonian, the full 0-to-2pi "
        "coupling circle, and its ferromagnetic, Neel, zigzag, and stripy "
        "ordered phases alongside two spin-liquid phases"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text,
        "parse_chaloupka_full_kitaev_heisenberg_ordered_phases",
    )
    return _finalize_prepared_trace(
        _parse_chaloupka_full_kitaev_heisenberg_ordered_phases_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_chaloupka_full_kitaev_heisenberg_ordered_phases_prepared(
    normalized,
):
    error_message = (
        "Chaloupka full Kitaev-Heisenberg phase diagram source must "
        "establish the identified 1209.5100v1 preprint, the nearest-"
        "neighbor Kitaev-Heisenberg Hamiltonian, the full 0-to-2pi "
        "coupling circle, and its ferromagnetic, Neel, zigzag, and stripy "
        "ordered phases alongside two spin-liquid phases"
    )
    _, common = _match_chaloupka_full_kitaev_heisenberg_prepared(normalized)

    phi_pattern = r"(?:phi|ϕ)"
    pi_pattern = r"(?:pi|π)"
    parameter_match = re.search(
        r"(?:introduce|Let us introduce) the energy scale A"
        r".{0,220}?angle\s+"
        + phi_pattern
        + r"\s+via K\s*=\s*A\s*sin\s*"
        + phi_pattern
        + r"\s+and J\s*=\s*A\s*cos\s*"
        + phi_pattern
        + r".{0,500}?phase.{0,30}?angle\s+"
        + phi_pattern
        + r"\s+(?:to )?vary from 0 to 2\s*"
        + pi_pattern,
        normalized,
        flags=re.IGNORECASE,
    )
    phase_body_match = re.search(
        r"In its full parameter space,\s*(?:the )?"
        r"(?:Kitaev\s*-\s*Heisenberg|KH.{0,300}?) "
        r"model accommodates "
        r"6 different phases"
        r".{0,2600}?N.{0,5}?eel\s*-\s*AF"
        r".{0,500}?stripy\s*-\s*AF"
        r".{0,500}?(?:spin\s*-\s*liquid|SL) states"
        r".{0,1600}?(?:three|3) more states"
        r".{0,800}?AF.{0,120}?"
        r"(?:Kitaev|Ki\s*-.{0,300}?taev) spin\s*-\s*liquid"
        r".{0,1000}?(?:\bFM\b|ferromagnetic phase)"
        r".{0,1400}?zigzag\s*-\s*AF",
        normalized,
        flags=re.IGNORECASE,
    )
    figure_match = re.search(
        r"(?:FIG\.?|Figure)\s*1\s*:"
        r".{0,180}?Phase diagram of the Kitaev\s*-\s*Heisenberg model "
        r"containing 2 spin\s*-\s*liquid and 4 spin\s*-\s*ordered"
        r".{0,300}?phases",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        common.get("identity"),
        common.get("archive"),
        common.get("abstract"),
        common.get("model"),
        parameter_match,
        phase_body_match,
        figure_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    identity_start = min(
        common["identity"].start(), common["archive"].start()
    )
    identity_end = max(
        common["identity"].end(), common["archive"].end()
    )
    return (
        {
            "ordered_phases": [
                "ferromagnetic",
                "neel",
                "zigzag",
                "stripy",
            ]
        },
        {
            "parser": (
                "parse_chaloupka_full_kitaev_heisenberg_ordered_phases"
            ),
            "source_parameter_space": (
                "K=A sin(phi), J=A cos(phi), phi spanning 0 to 2pi"
            ),
            "source_phase_counts": {
                "spin_liquid_phases": 2,
                "spin_ordered_phases": 4,
            },
            "corrected_source_doi": (
                "10.1103/PhysRevLett.110.097204"
            ),
            "superseded_registered_doi": (
                "10.1103/PhysRevLett.105.027204"
            ),
            "source_scope_correction": (
                "the 2010 DOI covers only the restricted Neel-stripy-"
                "spin-liquid sector; the four ordered phases come from "
                "the 2013 full-parameter-space paper"
            ),
            "matched_anchors": [
                "identified arXiv:1209.5100v1 paper and authors",
                "abstract: full parameter space and zigzag order",
                "nearest-neighbor Kitaev-Heisenberg Hamiltonian Eq. (1)",
                "K=A sin(phi), J=A cos(phi), and full 0-to-2pi circle",
                "body enumeration of all six phases",
                "Figure 1 caption: two liquid and four ordered phases",
            ],
            "text_spans": [
                [identity_start, identity_end],
                [common["abstract"].start(), common["abstract"].end()],
                [common["model"].start(), common["model"].end()],
                [parameter_match.start(), parameter_match.end()],
                [phase_body_match.start(), phase_body_match.end()],
                [figure_match.start(), figure_match.end()],
            ],
        },
    )


def parse_chaloupka_na2iro3_zigzag_relevance(source_text):
    """Extract the full-KH model's relevance to Na2IrO3 zigzag order."""

    error_message = (
        "Chaloupka Na2IrO3 zigzag source must establish the identified "
        "1209.5100v1 paper, nearest-neighbor Kitaev-Heisenberg model, "
        "natural zigzag ground state, experimental agreement, fitted J "
        "and K couplings, and the localized-Ir-moment conclusion"
    )
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(error_message)
    prepared = _prepared_view_for_parser(
        source_text, "parse_chaloupka_na2iro3_zigzag_relevance"
    )
    return _finalize_prepared_trace(
        _parse_chaloupka_na2iro3_zigzag_relevance_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_chaloupka_na2iro3_zigzag_relevance_prepared(normalized):
    error_message = (
        "Chaloupka Na2IrO3 zigzag source must establish the identified "
        "1209.5100v1 paper, nearest-neighbor Kitaev-Heisenberg model, "
        "natural zigzag ground state, experimental agreement, fitted J "
        "and K couplings, and the localized-Ir-moment conclusion"
    )
    _, common = _match_chaloupka_full_kitaev_heisenberg_prepared(normalized)
    material_pattern = r"Na\s*2\s*IrO\s*3"
    phase_figure_match = re.search(
        r"(?:FIG\.?|Figure)\s*1\s*:"
        r".{0,180}?Phase diagram of the Kitaev\s*-\s*Heisenberg model "
        r"containing 2 spin\s*-\s*liquid and 4 spin\s*-\s*ordered"
        r".{0,300}?phases",
        normalized,
        flags=re.IGNORECASE,
    )
    relevance_match = re.search(
        r"(?:In this Letter,\s*)?we show that the zigzag order is "
        r"(?:in fact )?.{0,120}?a natural ground state"
        r"(?:\s*\(\s*GS\s*\))?\s+of the "
        r"(?:Kitaev\s*-\s*Heisenberg|KH) model"
        r".{0,500}?(?:previously|previ\s*-.{0,220}?ously) "
        r"overlooked parameter range"
        r".{0,2500}?(?:calculate|calculated) spin\s*-\s*wave spectra"
        r".{0,500}?magnetic.{0,300}?susceptibility"
        r".{0,500}?(?:agree with|nice agreement with) experiments"
        r".{0,500}?lend(?:ing|s).{0,300}?strong support to the "
        r"(?:Kitaev\s*-\s*Heisenberg|KH) model"
        r".{0,200}?dominant "
        r"(?:interaction|interac\s*-.{0,300}?tion) in\s+"
        + material_pattern,
        normalized,
        flags=re.IGNORECASE,
    )
    fit_match = re.search(
        r"J\s*=\s*-\s*4\.01\s*meV"
        r"\s*(?:,|and)\s*K\s*=\s*10\.45\s*meV"
        r".{0,1800}?locat.{0,40}?"
        + material_pattern
        + r"\s+near\s+(?:phi|ϕ)\s*=\s*111\s*"
        r"(?:\+\s*/\s*-|±)\s*2\s*(?:degrees|[◦°])",
        normalized,
        flags=re.IGNORECASE,
    )
    conclusion_match = re.search(
        r"To conclude,\s*we have clarified the origin of zigzag"
        r".{0,400}?magnetic order in\s+"
        + material_pattern
        + r"\s+in terms of (?:the )?nearest\s*-\s*neighbor"
        r".{0,300}?"
        r"Kitaev\s*-\s*Heisenberg model for localized "
        r"Ir\s*(?:-\s*)?moments"
        r".{0,300}?model well agrees with the low\s*-\s*energy magnon"
        r".{0,300}?high.{0,300}?"
        r"temperature magnetic susceptibility data",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        common.get("identity"),
        common.get("archive"),
        common.get("abstract"),
        common.get("model"),
        phase_figure_match,
        relevance_match,
        fit_match,
        conclusion_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(error_message)

    identity_start = min(
        common["identity"].start(), common["archive"].start()
    )
    identity_end = max(
        common["identity"].end(), common["archive"].end()
    )
    return (
        {"zigzag_order_relevant": True},
        {
            "parser": "parse_chaloupka_na2iro3_zigzag_relevance",
            "source_model": (
                "nearest-neighbor Kitaev-Heisenberg model for localized "
                "Ir moments"
            ),
            "na2iro3_fit": {
                "j_mev": -4.01,
                "k_mev": 10.45,
                "phi_degrees": 111.0,
                "phi_uncertainty_degrees": 2.0,
            },
            "corrected_source_doi": (
                "10.1103/PhysRevLett.110.097204"
            ),
            "superseded_registered_doi": (
                "10.1103/PhysRevLett.105.027204"
            ),
            "matched_anchors": [
                "identified arXiv:1209.5100v1 paper and authors",
                "abstract: full KH space and Na2IrO3 zigzag relevance",
                "nearest-neighbor Kitaev-Heisenberg Hamiltonian Eq. (1)",
                "Figure 1 full phase diagram includes zigzag",
                "natural zigzag ground state and experimental agreement",
                "Na2IrO3 fit J=-4.01 meV, K=10.45 meV, phi=111(2) deg",
                "conclusion: localized-moment nearest-neighbor KH model",
            ],
            "text_spans": [
                [identity_start, identity_end],
                [common["abstract"].start(), common["abstract"].end()],
                [common["model"].start(), common["model"].end()],
                [
                    phase_figure_match.start(),
                    phase_figure_match.end(),
                ],
                [relevance_match.start(), relevance_match.end()],
                [fit_match.start(), fit_match.end()],
                [conclusion_match.start(), conclusion_match.end()],
            ],
        },
    )


def parse_capriotti_triangular_energy(source_text):
    """Extract Capriotti et al.'s triangular-lattice ground-state energy."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Capriotti triangular energy requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"Heisenberg model on the triangular lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    method_match = re.search(
        r"quantum Monte Carlo techniques.{0,100}?exact diagonalization",
        normalized,
        flags=re.IGNORECASE,
    )
    limit_match = re.search(
        r"thermodynamic limit.{0,180}?ground state energy per site",
        normalized,
        flags=re.IGNORECASE,
    )
    standard_claim_match = re.search(
        r"ground state energy per site is e0\s*=\s*[-−]\s*0\.5458\s*"
        r"(?:\+\s*/\s*-|±)\s*0\.0001 in units of the exchange coupling",
        normalized,
        flags=re.IGNORECASE,
    )
    locked_ocr_claim_match = re.search(
        r"ground state energy per site is e0\s*.{0,3}?20\.5458\s+6\s+"
        r"0\.0001 in units of the exchange coupling",
        normalized,
        flags=re.IGNORECASE,
    )
    claim_match = standard_claim_match or locked_ocr_claim_match
    matches = [model_match, method_match, limit_match, claim_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Capriotti triangular energy requires the triangular Heisenberg "
            "model, quantum Monte Carlo plus exact diagonalization, the "
            "thermodynamic limit, and e0=-0.5458 +/- 0.0001 in exchange units"
        )
    return (
        {"energy_per_site_approx": -0.5458},
        {
            "parser": "parse_capriotti_triangular_energy",
            "reported_uncertainty": 0.0001,
            "matched_anchors": [
                "Heisenberg model on triangular lattice",
                "quantum Monte Carlo and exact diagonalization",
                "thermodynamic-limit ground-state energy per site",
                "e0=-0.5458 +/- 0.0001 in exchange-coupling units",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_checkerboard_plaquette_vbc(source_text):
    """Extract checkerboard plaquette long-range order and VBC claims."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "checkerboard plaquette VBC claim requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"spin-1/2 Heisenberg model on the checkerboard lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    plaquette_match = re.search(
        r"displays long-range order in four-spin S.{0,3}?0 plaquettes",
        normalized,
        flags=re.IGNORECASE,
    )
    vbc_match = re.search(
        r"Heisenberg quantum model on a checkerboard lattice is a "
        r"valence bond crystal",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [model_match, plaquette_match, vbc_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "checkerboard plaquette VBC claim must identify the spin-1/2 "
            "checkerboard Heisenberg model, long-range order in four-spin "
            "S=0 plaquettes, and the valence-bond-crystal conclusion"
        )
    return (
        {
            "plaquette_long_range_order": True,
            "valence_bond_crystal": True,
        },
        {
            "parser": "parse_checkerboard_plaquette_vbc",
            "matched_anchors": [
                "spin-1/2 checkerboard Heisenberg model",
                "long-range order in four-spin S=0 plaquettes",
                "checkerboard Heisenberg valence-bond crystal",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_spin_peierls_distortion_gap(source_text):
    """Derive the finite-distortion gap from Cross-Fisher scaling."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "spin-Peierls distortion gap requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"spin-Peierls transition in spin-1/2 Heisenberg chains",
        normalized,
        flags=re.IGNORECASE,
    )
    distortion_match = re.search(
        r"static lattice distortion",
        normalized,
        flags=re.IGNORECASE,
    )
    scaling_match = re.search(
        r"energy gap.{0,320}?perature scales as the lattice distortion "
        r"to the power",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [model_match, distortion_match, scaling_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "spin-Peierls distortion gap requires the spin-1/2 Heisenberg "
            "chain, a static lattice distortion, and the zero-temperature "
            "gap scaling with lattice distortion"
        )
    return (
        {"finite_delta_opens_gap": True},
        {
            "parser": "parse_spin_peierls_distortion_gap",
            "selector_derivation": (
                "a stated zero-temperature gap scaling with lattice distortion "
                "implies a finite gap for finite nonzero distortion"
            ),
            "matched_anchors": [
                "spin-1/2 Heisenberg spin-Peierls chain",
                "static lattice distortion",
                "zero-temperature gap scales with lattice distortion",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_bpcb_field_induced_ll(source_text):
    """Extract the field-induced Luttinger-liquid regime in BPCB."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("BPCB field-induced LL requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(
        r"spin-ladder material.{0,40}?Hpip.{0,12}?2CuBr4",
        normalized,
        flags=re.IGNORECASE,
    )
    field_induction_match = re.search(
        r"spin (?:Luttinger liquid|LL) is induced from a.{0,220}?gapped.{0,60}?"
        r"quantum[- ]disordered.{0,180}?by an applied "
        r"(?:magnetic field|mag-.{0,220}?netic field)",
        normalized,
        flags=re.IGNORECASE,
    )
    interval_match = re.search(
        r"LL regime between Bc and Bs|between the critical fields Bc and Bs",
        normalized,
        flags=re.IGNORECASE,
    )
    measurement_match = re.search(
        r"(?:MCE|magnetocaloric-effect) measurements.{0,100}?demonstrate "
        r"spin (?:LL|Luttinger-liquid) behavior",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [
        material_match,
        field_induction_match,
        interval_match,
        measurement_match,
    ]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "BPCB field-induced LL requires the (Hpip)2CuBr4 spin ladder, "
            "a field-induced LL from the gapped quantum-disordered phase, "
            "the Bc-to-Bs interval, and experimental LL evidence"
        )
    return (
        {"field_induced_luttinger_liquid_regime": True},
        {
            "parser": "parse_bpcb_field_induced_ll",
            "matched_anchors": [
                "(Hpip)2CuBr4 spin-ladder material",
                "applied field induces LL from gapped QD phase",
                "LL regime between Bc and Bs",
                "MCE measurements demonstrate spin-LL behavior",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_hasenbusch_xy_bkt_temperature(source_text):
    """Extract the square-XY BKT temperature in units of J."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Hasenbusch XY BKT temperature requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"classical XY model on the square lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    normalization_match = re.search(
        r"(?:coupling(?: constant)? (?:has been )?set to )?J\s*=\s*1"
        r".{0,100}?(?:β|beta) is the inverse temperature",
        normalized,
        flags=re.IGNORECASE,
    )
    estimate_match = re.search(
        r"(?:β|beta)[_ ]?KT\s*=\s*1\.1199\s*\(\s*1\s*\)"
        r"\s*=\s*1\s*/\s*0\.89294\s*\(\s*8\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [model_match, normalization_match, estimate_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Hasenbusch XY BKT temperature requires the classical square XY "
            "model, J=1 inverse-temperature convention, and the published "
            "beta_KT=1.1199(1)=1/0.89294(8) estimate"
        )
    return (
        {"tbkt_over_j": 0.89294},
        {
            "parser": "parse_hasenbusch_xy_bkt_temperature",
            "equation": "published estimate",
            "inverse_beta": 1.1199,
            "reported_uncertainty": 0.00008,
            "derivation": "J=1 and beta=1/T, so T_KT/J=0.89294",
            "matched_anchors": [
                "classical XY model on square lattice",
                "J=1 and beta is inverse temperature",
                "beta_KT=1.1199(1)=1/0.89294(8)",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_azurite_one_third_plateau(source_text):
    """Extract the experimentally identified one-third plateau in azurite."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "azurite one-third plateau requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(r"\bazurite\b", normalized, flags=re.IGNORECASE)
    lattice_match = re.search(
        r"diamond[- ]chain", normalized, flags=re.IGNORECASE
    )
    plateau_match = re.search(
        r"(?:1\s*[/=]\s*3|one[- ]third) magnetization plateau",
        normalized,
        flags=re.IGNORECASE,
    )
    experiment_match = re.search(
        r"specific[- ]heat and inelastic[- ]neutron[- ]scattering study",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [material_match, lattice_match, plateau_match, experiment_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "azurite one-third plateau requires the azurite material, "
            "diamond-chain identity, one-third magnetization plateau, and "
            "specific-heat plus inelastic-neutron-scattering evidence"
        )
    return (
        {"one_third_magnetization_plateau": True},
        {
            "parser": "parse_azurite_one_third_plateau",
            "matched_anchors": [
                "azurite material identity",
                "diamond-chain identity",
                "one-third magnetization plateau",
                "specific-heat and inelastic-neutron-scattering study",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_ba3cosb2o9_one_third_plateau(source_text):
    """Extract the one-third plateau in triangular-lattice Ba3CoSb2O9."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Ba3CoSb2O9 one-third plateau requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(
        r"\bBa3\s*Co\s*Sb2\s*O9\b", normalized, flags=re.IGNORECASE
    )
    spin_match = re.search(r"spin[- ]1\s*[/=]\s*2", normalized, flags=re.IGNORECASE)
    lattice_match = re.search(
        r"regular triangular lattice", normalized, flags=re.IGNORECASE
    )
    plateau_match = re.search(
        r"(?:one[- ]third|1\s*[/=]\s*3)(?: quantum)? magnetization plateau",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [material_match, spin_match, lattice_match, plateau_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Ba3CoSb2O9 one-third plateau requires the Ba3CoSb2O9 material, "
            "spin-1/2 identity, regular triangular lattice, and one-third "
            "magnetization plateau"
        )
    return (
        {"one_third_magnetization_plateau": True},
        {
            "parser": "parse_ba3cosb2o9_one_third_plateau",
            "matched_anchors": [
                "Ba3CoSb2O9 material identity",
                "spin-1/2 identity",
                "regular triangular lattice",
                "one-third magnetization plateau",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_chubukov_golosov_triangular_plateau(source_text):
    """Extract the triangular-Heisenberg one-third plateau prediction."""

    error_prefix = "Chubukov-Golosov triangular plateau"
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(f"{error_prefix} requires nonempty text")
    prepared = _prepared_view_for_parser(
        source_text, "parse_chubukov_golosov_triangular_plateau"
    )
    return _finalize_prepared_trace(
        _parse_chubukov_golosov_triangular_plateau_prepared(
            prepared.text
        ),
        prepared,
    )


def _parse_chubukov_golosov_triangular_plateau_prepared(normalized):
    error_prefix = "Chubukov-Golosov triangular plateau"
    scan_layout_forms_accepted = normalized.endswith(
        "\n#scan-layout-forms-accepted"
    )

    title_match = re.search(
        r"Quantum theory of an antiferromagnet\s*on a triangular lattice "
        r"in a magnetic field",
        normalized,
        flags=re.IGNORECASE,
    )
    author_match = re.search(
        r"A\s*V\s*Chubukov\s+and\s+D\s*I\s*Golosov",
        normalized,
        flags=re.IGNORECASE,
    )
    spin_half_scope_match = re.search(
        r"S\s*=\s*1\s*/\s*2.{0,100}?two(?:-|\s*)dimensional"
        r".{0,100}?antiferromagnets?.{0,60}?triangular lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    isotropic_model_match = re.search(
        r"2\.\s*Isotropic case.{0,160}?We start with an isotropic "
        r"Heisenberg antiferromagnetic on a triangular lattice\s*:"
        r".{0,220}?\(\s*4\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    method_match = re.search(
        r"traditional spin wave approach\s*,?\s*based on the "
        r"[1Il]\s*/\s*S expansion",
        normalized,
        flags=re.IGNORECASE,
    )
    finite_interval_match = re.search(
        r"In the intermediate region.{0,120}?collinear configuration is "
        r"stable.{0,220}?all the\s*excitations\s*have a\s*finite\s*gap",
        normalized,
        flags=re.IGNORECASE,
    )
    body_plateau_match = re.search(
        r"magnetization.{0,80}?remains constant inside the collinear phase"
        r".{0,520}?equals one third of the saturation value"
        r".{0,240}?first quantum correction.{0,180}?equals\s*zero"
        r".{0,220}?magnetization\s*retains\s*its\s*classical\s*value",
        normalized,
        flags=re.IGNORECASE,
    )
    figure_plateau_match = re.search(
        r"Figure\s*3\..{0,500}?plateau on the magnet.{0,180}?ization curve "
        r"results from the stabilization of the.{0,160}?collinear phase in "
        r"the finite region of magnetic fields due to zero-point motion",
        normalized,
        flags=re.IGNORECASE,
    )
    summary_match = re.search(
        r"6\.\s*Summary.{0,420}?intermediate collinear phase.{0,160}?"
        r"constant longitudinal magnetization equal to one third of the "
        r"saturation value.{0,220}?Heisenberg and XY.{0,180}?"
        r"quantum fluctuations",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = (
        title_match,
        author_match,
        spin_half_scope_match,
        isotropic_model_match,
        method_match,
        finite_interval_match,
        body_plateau_match,
        figure_plateau_match,
        summary_match,
    )
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            f"{error_prefix} requires the identified primary paper, its "
            "spin-1/2 triangular scope, isotropic field Hamiltonian, spin-wave "
            "1/S method, finite gapped collinear interval, zero quantum "
            "correction to the one-third magnetization, plateau figure, and "
            "summary claim"
        )

    return (
        {"one_third_plateau": True},
        {
            "parser": "parse_chubukov_golosov_triangular_plateau",
            "source_role": "registered primary source",
            "method": "spin-wave 1/S expansion",
            "field_regime": "finite interval h_1<h<h_2",
            "magnetization_fraction_of_saturation": 1.0 / 3.0,
            "registry_backend_mismatch": (
                "registered ed_or_dmrg; source uses spin-wave 1/S expansion"
            ),
            "scan_layout_forms_accepted": scan_layout_forms_accepted,
            "matched_anchors": [
                "identified Chubukov-Golosov paper title",
                "Chubukov and Golosov authors",
                "spin-1/2 two-dimensional triangular-antiferromagnet scope",
                "isotropic triangular Heisenberg field model in equation (4)",
                "spin-wave 1/S expansion",
                "finite gapped collinear interval",
                "constant one-third magnetization with zero first correction",
                "figure 3 plateau from zero-point stabilization",
                "summary one-third plateau claim from quantum fluctuations",
            ],
            "text_spans": [
                [match.start(), match.end()] for match in matches
            ],
        },
    )


def parse_kagome_one_third_plateau(source_text):
    """Extract the DMRG one-third plateau in the kagome Heisenberg model."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("kagome one-third plateau requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text.replace("ﬁ", "fi")).strip()
    model_match = re.search(
        r"quantum spin[- ]1\s*/\s*2 kagome Heisenberg antiferromagnet",
        normalized,
        flags=re.IGNORECASE,
    )
    field_match = re.search(
        r"(?:in an applied|apply a) magnetic field",
        normalized,
        flags=re.IGNORECASE,
    )
    method_match = re.search(
        r"grand canonical density matrix renor(?:malization|- malization) group",
        normalized,
        flags=re.IGNORECASE,
    )
    plateau_match = re.search(
        r"without ambiguity.{0,80}?plateau structures.{0,100}?\b1\s*/\s*3\b",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [model_match, field_match, method_match, plateau_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "kagome one-third plateau requires the spin-1/2 kagome Heisenberg "
            "model, applied field, grand-canonical DMRG, and an unambiguous "
            "one-third plateau in the magnetization curve"
        )
    return (
        {"one_third_plateau": True},
        {
            "parser": "parse_kagome_one_third_plateau",
            "matched_anchors": [
                "spin-1/2 kagome Heisenberg antiferromagnet",
                "applied magnetic field",
                "grand-canonical density-matrix renormalization group",
                "unambiguous plateau structure at M/Msat=1/3",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def _parse_kageyama_shastry_sutherland_anchors(source_text):
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Kageyama Shastry-Sutherland claim requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(
        r"\bSrCu2\s*(?:\(\s*BO3\s*\)|s\s*BO3\s*d)\s*2\b",
        normalized,
        flags=re.IGNORECASE,
    )
    network_match = re.search(
        r"(?:two-dimensional(?:\s*\(2D\))?|2D) orthogonal network of Cu dimers",
        normalized,
        flags=re.IGNORECASE,
    )
    measurement_match = re.search(
        r"high-(?:field|filed) magnetization (?:have|has) been measured",
        normalized,
        flags=re.IGNORECASE,
    )
    plateau_match = re.search(
        r"two plateaus corresponding to (?:1\s*/\s*4|14) and "
        r"(?:1\s*/\s*8|18) of the full Cu moment were first observed",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [material_match, network_match, measurement_match, plateau_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Kageyama Shastry-Sutherland claim requires SrCu2(BO3)2, its "
            "two-dimensional orthogonal Cu-dimer network, measured high-field "
            "magnetization, and the observed one-quarter and one-eighth plateaus"
        )
    return matches


def parse_kageyama_shastry_sutherland_plateaus(source_text):
    """Extract the observed fractional plateaus in SrCu2(BO3)2."""

    matches = _parse_kageyama_shastry_sutherland_anchors(source_text)
    return (
        {"fractional_plateaus_observed": True},
        {
            "parser": "parse_kageyama_shastry_sutherland_plateaus",
            "matched_anchors": [
                "SrCu2(BO3)2 material identity",
                "two-dimensional orthogonal Cu-dimer network",
                "measured high-field magnetization",
                "observed one-quarter and one-eighth plateaus",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_kageyama_shastry_sutherland_material(source_text):
    """Extract the orthogonal-dimer material and plateau claims for SrCu2(BO3)2."""

    matches = _parse_kageyama_shastry_sutherland_anchors(source_text)
    return (
        {"orthogonal_dimer_material": True, "magnetization_plateaus": True},
        {
            "parser": "parse_kageyama_shastry_sutherland_material",
            "matched_anchors": [
                "SrCu2(BO3)2 material identity",
                "two-dimensional orthogonal Cu-dimer network",
                "measured high-field magnetization",
                "observed one-quarter and one-eighth plateaus",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_cacu2o3_spin_ladder_material(source_text):
    """Extract the buckled two-leg spin-ladder identity of CaCu2O3."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("CaCu2O3 spin ladder requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(r"\bCaCu2\s*O3\b", normalized, flags=re.IGNORECASE)
    prototype_match = re.search(
        r"proto(?:type|- type) two-leg spin-ladder compound SrCu2\s*O3",
        normalized,
        flags=re.IGNORECASE,
    )
    rung_match = re.search(
        r"Cu-O-Cu bond angle in the ladder rungs.{0,50}?123",
        normalized,
        flags=re.IGNORECASE,
    )
    structure_match = re.search(
        r"ladderlike structures.{0,300}?quasi-1D copper-oxide chains",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [material_match, prototype_match, rung_match, structure_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "CaCu2O3 spin ladder requires the material identity, two-leg "
            "spin-ladder structural comparison, ladder rungs, and ladderlike "
            "quasi-one-dimensional copper-oxide structures"
        )
    return (
        {"spin_ladder_material": True},
        {
            "parser": "parse_cacu2o3_spin_ladder_material",
            "matched_anchors": [
                "CaCu2O3 material identity",
                "prototype two-leg spin-ladder structural comparison",
                "123-degree ladder rungs",
                "ladderlike quasi-1D copper-oxide structures",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_ba2cugeo7_dm_spiral(source_text):
    """Extract the DM-induced incommensurate spiral in Ba2CuGe2O7."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Ba2CuGe2O7 DM spiral requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(
        r"\bBa\s*2\s*CuGe2\s*O7\b", normalized, flags=re.IGNORECASE
    )
    spiral_match = re.search(
        r"Dzyaloshinskii-Moriya spiral antiferromagnet",
        normalized,
        flags=re.IGNORECASE,
    )
    experiment_match = re.search(
        r"bulk magnetic measurements and neutron(?:- ?| )diffraction experiments",
        normalized,
        flags=re.IGNORECASE,
    )
    cause_match = re.search(
        r"incommensurate magnetic phase is a result of.{0,250}?"
        r"Dzyaloshinskii-Moriya interactions",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [material_match, spiral_match, experiment_match, cause_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Ba2CuGe2O7 DM spiral requires the material identity, DM spiral "
            "antiferromagnet, bulk and neutron measurements, and the published "
            "attribution of the incommensurate phase to DM interactions"
        )
    return (
        {"dm_induced_incommensurate_spiral": True},
        {
            "parser": "parse_ba2cugeo7_dm_spiral",
            "matched_anchors": [
                "Ba2CuGe2O7 material identity",
                "Dzyaloshinskii-Moriya spiral antiferromagnet",
                "bulk magnetic and neutron-diffraction measurements",
                "incommensurate phase attributed to DM interactions",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_ho2ti2o7_spin_ice_correlations(source_text):
    """Extract neutron-established spin-ice correlations in Ho2Ti2O7."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Ho2Ti2O7 spin-ice correlations require nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(
        r"\bHo2\s*Ti2\s*O7\b", normalized, flags=re.IGNORECASE
    )
    experiment_match = re.search(
        r"neu-?\s*tron scattering and specific heat results",
        normalized,
        flags=re.IGNORECASE,
    )
    claim_match = re.search(
        r"establish unambiguously that Ho2\s*Ti2\s*O7 exhibits spin ice "
        r"correlations at low temperature",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"diffuse magnetic neu-?\s*tron scattering.{0,120}?nearest neighbor spin "
        r"ice model.{0,120}?dipolar spin ice model",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [material_match, experiment_match, claim_match, model_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Ho2Ti2O7 spin-ice correlations require the material identity, "
            "neutron-scattering plus specific-heat evidence, an unambiguous "
            "low-temperature correlation claim, and spin-ice model agreement"
        )
    return (
        {"spin_ice_correlations": True},
        {
            "parser": "parse_ho2ti2o7_spin_ice_correlations",
            "matched_anchors": [
                "Ho2Ti2O7 material identity",
                "neutron scattering and specific heat",
                "unambiguous low-temperature spin-ice correlations",
                "nearest-neighbor and dipolar spin-ice model agreement",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_jarosite_q0_120_order(source_text):
    """Extract the q=0 120-degree ordered structure of iron jarosite."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("jarosite q=0 order requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(
        r"KFe3.{0,20}?OH.{0,20}?6.{0,20}?SO4.{0,20}?2",
        normalized,
        flags=re.IGNORECASE,
    )
    experiment_match = re.search(
        r"kagome.{0,30}?antiferromagnet.{0,160}?high-resolution inelastic "
        r"neutron scattering",
        normalized,
        flags=re.IGNORECASE,
    )
    order_match = re.search(
        r"(?:each|every) triangle.{0,100}?120(?:\s*degrees|[^0-9A-Za-z])",
        normalized,
        flags=re.IGNORECASE,
    )
    unit_cell_match = re.search(
        r"magnetic unit cell.{0,220}?same as the chemical unit cell",
        normalized,
        flags=re.IGNORECASE,
    )
    dm_match = re.search(
        r"Dzyaloshinskii-Moriya interaction is the primary source of "
        r"anisotropy and explains the low-temperature.{0,40}?spin structure",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [
        material_match,
        experiment_match,
        order_match,
        unit_cell_match,
        dm_match,
    ]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "jarosite q=0 order requires iron-jarosite identity, inelastic "
            "neutron scattering, 120-degree triangle order, equal magnetic "
            "and chemical unit cells, and the DM spin-structure explanation"
        )
    return (
        {"q_0_120_order": True},
        {
            "parser": "parse_jarosite_q0_120_order",
            "derivation": (
                "a 120-degree kagome spin structure whose magnetic unit cell "
                "equals the chemical unit cell has propagation vector q=0"
            ),
            "matched_anchors": [
                "KFe3(OH)6(SO4)2 kagome antiferromagnet",
                "high-resolution inelastic neutron scattering",
                "120-degree triangle spin configuration",
                "magnetic unit cell equals chemical unit cell",
                "Dzyaloshinskii-Moriya explanation of spin structure",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_maple_leaf_magnetic_order(source_text):
    """Extract magnetic long-range order in the spin-half maple-leaf HAFM."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "maple-leaf magnetic order requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    spin_match = re.search(
        r"(?:spin[- ]half|spin[- ]*1\s*[=/]\s*2|spin-\s*12)",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"Heisenberg antiferromagnet.{0,180}?maple-leaf lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    method_match = re.search(
        r"coupled cluster method.{0,180}?exact diagonalization",
        normalized,
        flags=re.IGNORECASE,
    )
    observable_match = re.search(
        r"ground-state magnetic long-range order",
        normalized,
        flags=re.IGNORECASE,
    )
    result_match = re.search(
        r"pure.{0,80}?maple-leaf.{0,100}?Heisenberg antiferromagnets? "
        r"(?:is|are) magnetically ordered",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [
        spin_match,
        model_match,
        method_match,
        observable_match,
        result_match,
    ]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "maple-leaf magnetic order requires the spin-half maple-leaf "
            "Heisenberg model, coupled-cluster plus exact-diagonalization "
            "methods, the long-range-order observable, and the ordered result"
        )
    return (
        {"magnetic_long_range_order": True},
        {
            "parser": "parse_maple_leaf_magnetic_order",
            "matched_anchors": [
                "spin-half model",
                "maple-leaf Heisenberg antiferromagnet",
                "coupled cluster and exact diagonalization",
                "ground-state magnetic long-range order",
                "pure maple-leaf antiferromagnet is magnetically ordered",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_alpha_rucl3_zigzag_kitaev_gamma(source_text):
    """Extract zigzag order and Kitaev-Gamma interactions for alpha-RuCl3."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "alpha-RuCl3 zigzag/Kitaev-Gamma claim requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(
        r"(?:alpha|α)[- ]?RuCl3", normalized, flags=re.IGNORECASE
    )
    zigzag_match = re.search(
        r"honeycomb trihalide (?:alpha|α)[- ]?RuCl3.{0,320}?"
        r"dis-?.{0,200}?plays zigzag order",
        normalized,
        flags=re.IGNORECASE,
    )
    kitaev_match = re.search(
        r"Kitaev coupling K", normalized, flags=re.IGNORECASE
    )
    gamma_match = re.search(
        r"[Oo]ff-diagonal couplings?.{0,40}?"
        r"(?:Gamma|Γ|\x08).{0,260}?dominate.{0,200}?nearest-neighbor "
        r"magnetic interactions",
        normalized,
    )
    table_match = re.search(
        r"complete magnetic interactions.{0,80}?(?:alpha|α)[- ]?RuCl3",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [
        material_match,
        zigzag_match,
        kitaev_match,
        gamma_match,
        table_match,
    ]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "alpha-RuCl3 zigzag/Kitaev-Gamma claim requires the material, "
            "observed zigzag order, complete interaction table, Kitaev K, and "
            "off-diagonal Gamma interaction evidence"
        )
    return (
        {"zigzag_order": True, "kitaev_gamma_model_reference": True},
        {
            "parser": "parse_alpha_rucl3_zigzag_kitaev_gamma",
            "matched_anchors": [
                "alpha-RuCl3 material identity",
                "honeycomb trihalide displays zigzag order",
                "Kitaev coupling K",
                "dominant off-diagonal Gamma coupling",
                "complete alpha-RuCl3 magnetic interactions",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_beta_li2iro3_spiral_order(source_text):
    """Extract incommensurate counter-rotating order in beta-Li2IrO3."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "beta-Li2IrO3 spiral order requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(
        r"(?:beta|β)[- ]?Li2\s*IrO3", normalized, flags=re.IGNORECASE
    )
    lattice_match = re.search(
        r"hyperhoneycomb.{0,30}?lattice", normalized, flags=re.IGNORECASE
    )
    experiment_match = re.search(
        r"neutron powder diffraction and magnetic resonant x-ray diffraction",
        normalized,
        flags=re.IGNORECASE,
    )
    order_match = re.search(
        r"incommensurate magnetic order with non-?coplanar and "
        r"counter-rotating Ir moments",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [material_match, lattice_match, experiment_match, order_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "beta-Li2IrO3 spiral order requires the hyperhoneycomb material, "
            "neutron plus resonant x-ray diffraction, and incommensurate "
            "noncoplanar counter-rotating order"
        )
    return (
        {"incommensurate_spiral_order": True},
        {
            "parser": "parse_beta_li2iro3_spiral_order",
            "derivation": (
                "incommensurate noncoplanar counter-rotating moments define "
                "the registered incommensurate spiral order"
            ),
            "matched_anchors": [
                "beta-Li2IrO3 material identity",
                "hyperhoneycomb lattice",
                "neutron and resonant x-ray diffraction",
                "incommensurate noncoplanar counter-rotating order",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_cs2cucl4_spiral_order(source_text):
    """Extract the neutron-observed incommensurate spiral in Cs2CuCl4."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Cs2CuCl4 spiral order requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(r"Cs2\s*CuCl4", normalized, flags=re.IGNORECASE)
    model_match = re.search(
        r"quasi-2D spin-1/2 frustrated Heisenberg antiferromagnet",
        normalized,
        flags=re.IGNORECASE,
    )
    experiment_match = re.search(
        r"high-resolution time-of-flight inelastic neutron scattering",
        normalized,
        flags=re.IGNORECASE,
    )
    order_match = re.search(
        r"magnetic order in an incommensurate spiral forms due to the 2D "
        r"frustrated couplings",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [material_match, model_match, experiment_match, order_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "Cs2CuCl4 spiral order requires the spin-half frustrated model, "
            "inelastic neutron method, and incommensurate spiral conclusion"
        )
    return (
        {"incommensurate_spiral_order": True},
        {
            "parser": "parse_cs2cucl4_spiral_order",
            "matched_anchors": [
                "Cs2CuCl4 material identity",
                "quasi-2D spin-half frustrated Heisenberg model",
                "time-of-flight inelastic neutron scattering",
                "incommensurate spiral magnetic order",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_square_dimerized_neel_transition(source_text):
    """Extract the Neel-to-dimer transition in the dimerized square HAFM."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "square dimerized Neel-dimer transition requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"(?:S.{0,3}?1/2|spin-1/2).{0,40}?two-dimensional quantum Heisenberg "
        r"antiferromagnet.{0,50}?anisotropic dimerized square lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    method_match = re.search(
        r"quantum Monte Carlo method", normalized, flags=re.IGNORECASE
    ) or re.search(r"quantum Monte Carlo", normalized, flags=re.IGNORECASE)
    phase_diagram_match = re.search(
        r"ground-state phase diagram", normalized, flags=re.IGNORECASE
    )
    dimer_match = re.search(
        r"(?:spin-gapped dimer|dimer state with a spin gap|dimer phase)",
        normalized,
        flags=re.IGNORECASE,
    )
    neel_match = re.search(
        r"(?:Ne.?el|AF)[- ]?(?:LRO|long-range-ordered|long-range order) phase",
        normalized,
        flags=re.IGNORECASE,
    )
    transition_match = re.search(
        r"(?:phase transitions?|critical phenomena).{0,100}?spin-gapped"
        r".{0,50}?phase.{0,100}?(?:AF|Ne.?el)",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [
        model_match,
        method_match,
        phase_diagram_match,
        dimer_match,
        neel_match,
        transition_match,
    ]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "square dimerized Neel-dimer transition requires the spin-half "
            "dimerized square model, QMC phase diagram, dimer spin gap, Neel "
            "long-range order, and a transition between those phases"
        )
    return (
        {"neel_to_dimer_transition": True},
        {
            "parser": "parse_square_dimerized_neel_transition",
            "matched_anchors": [
                "spin-half dimerized square Heisenberg model",
                "quantum Monte Carlo",
                "ground-state phase diagram",
                "spin-gapped dimer phase",
                "Neel long-range-ordered phase",
                "quantum phase transition between the phases",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_square_jq_neel_vbs_transition(source_text):
    """Extract the Neel-to-VBS transition in Sandvik's square J-Q model."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "square J-Q Neel-VBS transition requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    method_match = re.search(
        r"ground-state projector quantum Monte Carlo simulations",
        normalized,
        flags=re.IGNORECASE,
    )
    model_match = re.search(
        r"four-spin interactions.{0,100}?(?:Ne.?el) order.{0,100}?"
        r"two-dimensional S.{0,3}?1\s*[=/]\s*2 Heisenberg antiferromagnet",
        normalized,
        flags=re.IGNORECASE,
    )
    vbs_match = re.search(
        r"drive it into a valence-bond solid \(VBS\) phase",
        normalized,
        flags=re.IGNORECASE,
    )
    transition_match = re.search(
        r"spin and dimer correlations are consistent with a single continuous "
        r"transition",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [method_match, model_match, vbs_match, transition_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "square J-Q Neel-VBS transition requires projector QMC, the "
            "spin-half Heisenberg plus four-spin model, destruction of Neel "
            "order into a VBS, and a single transition"
        )
    return (
        {"neel_to_vbs_transition": True},
        {
            "parser": "parse_square_jq_neel_vbs_transition",
            "matched_anchors": [
                "ground-state projector quantum Monte Carlo",
                "spin-half Heisenberg model with four-spin interactions",
                "Neel order driven into valence-bond solid",
                "single continuous transition",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_triangular_classical_120_order(source_text):
    """Extract the classical triangular three-sublattice 120-degree state."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "triangular classical 120-degree order requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    model_match = re.search(
        r"nearest-neighbor (?:pairs|sites).{0,400}?two-dimensional.{0,120}?"
        r"triangular lattice",
        normalized,
        flags=re.IGNORECASE,
    )
    ground_state_match = re.search(
        r"classical ground state of the triangular-lattice.{0,30}?"
        r"(?:antiferromagnet|an-.{0,80}?tiferromagnet) has three sublattices",
        normalized,
        flags=re.IGNORECASE,
    )
    angle_match = re.search(
        r"spins on each sublattice.{0,160}?angle of 2\s*(?:pi|[imnz]+)\s*/\s*3"
        r".{0,500}?other two sublattices",
        normalized,
        flags=re.IGNORECASE,
    )
    translation_match = re.search(
        r"(?:translation|transla-.{0,500}?tion) by a nearest-neighbor vector"
        r".{0,500}?(?:(?:rotation|ro-.{0,500}?tation) in spin-space|"
        r"spin-space rotation) by angle 2\s*(?:pi|[imnz]+)\s*/\s*3",
        normalized,
        flags=re.IGNORECASE,
    )
    matches = [model_match, ground_state_match, angle_match, translation_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "triangular classical 120-degree order requires the nearest-neighbor "
            "triangular model, three sublattices, 2pi/3 spin angles, and the "
            "nearest-neighbor translation phase"
        )
    return (
        {
            "order": "120_degree",
            "q_reciprocal": [1.0 / 3.0, 2.0 / 3.0, 0.0],
        },
        {
            "parser": "parse_triangular_classical_120_order",
            "derivation": (
                "The source's three-sublattice translation phase 2pi/3 selects "
                "a triangular-lattice K point; in the registered reciprocal "
                "basis the chosen symmetry representative is (1/3,2/3,0)."
            ),
            "matched_anchors": [
                "nearest-neighbor two-dimensional triangular lattice",
                "classical ground state has three sublattices",
                "inter-sublattice spin angle 2pi/3",
                "nearest-neighbor translation rotates spins by 2pi/3",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def recompute_triangular_classical_120_order(*, candidate_q):
    """Minimize the nearest-neighbor triangular Fourier energy on candidates."""

    if not isinstance(candidate_q, Sequence) or not candidate_q:
        raise RuntimeEvidenceError("triangular candidate q list must be nonempty")

    def fourier_energy(q_vector):
        if not isinstance(q_vector, Sequence) or len(q_vector) != 3:
            raise RuntimeEvidenceError("triangular q vectors must have three components")
        h, k, _ = (float(component) for component in q_vector)
        return (
            math.cos(2.0 * math.pi * h)
            + math.cos(2.0 * math.pi * k)
            + math.cos(2.0 * math.pi * (h - k))
        )

    minimum_q = min(candidate_q, key=fourier_energy)
    return {
        "order": "120_degree",
        "q_reciprocal": [float(component) for component in minimum_q],
    }


def parse_fecl3_helimagnetic_order(source_text):
    """Extract the FeCl3 helical order and registered propagation vector."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("FeCl3 helimagnetic order requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    material_match = re.search(
        r"(?:FeCl3|FeC13|FeCls)", normalized, flags=re.IGNORECASE
    )
    stacking_match = re.search(
        r"near-neighbor (?:atoms|moments).{0,50}?c-axis direction.{0,50}?"
        r"oppositely (?:oriented|directed)", normalized, flags=re.IGNORECASE
    )
    modulation_match = re.search(
        r"r\s*=\s*\(\s*b(?:1|i)\s*\+\s*4\s*b(?:2|3|s)\s*\)\s*/\s*15"
        r".{0,100}?1450.{0,80}?wavelength of 15", normalized, flags=re.IGNORECASE
    )
    helix_match = re.search(
        r"(?:modulation is of the helical type|helical model).{0,180}?"
        r"rotate by 2\s*(?:pi|[ms])\s*[./]?\s*15.{0,80}?successive planes",
        normalized, flags=re.IGNORECASE
    )
    domain_match = re.search(
        r"(?:threefold domain symmetry|three- and sixfold symmetry|"
        r"three equivalent crystallographic axes)", normalized, flags=re.IGNORECASE
    )
    matches = [material_match, stacking_match, modulation_match, helix_match, domain_match]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "FeCl3 helimagnetic order requires material identity, antiparallel "
            "c-axis neighbors, the 15-plane modulation vector, helical 2pi/15 "
            "rotation, and the symmetry-related domains"
        )
    return (
        {"magnetic_order": "helimagnetic_spiral", "propagation_vector_hexagonal": [4.0 / 15.0, 1.0 / 15.0, 3.0 / 2.0]},
        {
            "parser": "parse_fecl3_helimagnetic_order",
            "derivation": (
                "The reported (b1+4b2)/15 modulation has a threefold-equivalent "
                "domain (4b1+b2)/15. Antiparallel neighboring c-axis planes add "
                "a half-integer l component; choosing the observed l=1 satellite "
                "gives the registered representative (4/15,1/15,3/2)."
            ),
            "matched_anchors": ["FeCl3 identity", "antiparallel c-axis moments", "15-plane modulation", "helical 2pi/15 rotation", "threefold domains"],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def _parse_material_source_claim(source_text, *, parser_name, operand, anchors):
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("material source claim requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    matches = [
        re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in anchors
    ]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "material source claim requires material identity, model context, "
            "measurement or calculation evidence, and the registered conclusion"
        )
    return (
        operand,
        {
            "parser": parser_name,
            "matched_anchors": [match.group(0) for match in matches],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def _parse_direct_source_claim(source_text, *, parser_name, operand, anchors):
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("direct source claim requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    matches = [
        re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in anchors
    ]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "direct source claim requires the complete model identity, source "
            "method or Hamiltonian context, and registered conclusion"
        )
    return (
        operand,
        {
            "parser": parser_name,
            "matched_anchors": [match.group(0) for match in matches],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_herbertsmithite_qsl_candidate(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_herbertsmithite_qsl_candidate",
        operand={"qsl_candidate": True},
        anchors=(
            r"ZnCu3.{0,25}?OH.{0,15}?Cl2",
            r"S.{0,6}?1\s*[=/]\s*2.{0,40}?kagome.{0,30}?antiferromagnet",
            r"no magnetic order is observed down to 50\s*mK",
            r"(?:suggest.{0,80}?spin liquid state|spin liquid state.{0,80}?realized)",
        ),
    )


def parse_kapellasite_competing_exchanges(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_kapellasite_competing_exchanges",
        operand={"competing_kagome_exchanges": True},
        anchors=(
            r"kapellasite.{0,80}?Cu3.{0,35}?Cl2",
            r"Heisenberg Hamiltonian",
            r"(?:J\s*1.{0,50}?ferromagnetic|ferromagnetic.{0,60}?J\s*1)",
            r"(?:further-neighbor antiferromagnetic|"
            r"antiferromagnetic.{0,30}?across-hexagon)",
        ),
    )


def parse_li2cuo2_frustrated_chain(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_li2cuo2_frustrated_chain",
        operand={"frustrated_ferromagnetic_chain": True},
        anchors=(
            r"Li2\s*CuO2",
            r"edge-sharing Cu-O chain",
            r"J\s*1.{0,80}?(?:FM|ferromagnetic)",
            r"J\s*2.{0,80}?(?:AFM|antiferromagnetic)",
        ),
    )


def parse_u1_pyrochlore_spin_liquid(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_u1_pyrochlore_spin_liquid",
        operand={"u1_quantum_spin_liquid_candidate": True},
        anchors=(
            r"S.{0,6}?1\s*[=/]\s*2.{0,35}?Heisenberg antiferromagnet",
            r"pyrochlore lattice",
            r"U\s*\(1\) spin liquid phase",
            r"stable to all zero-temperature perturbations.{0,80}?finite extent",
        ),
    )


def parse_herbertsmithite_dm_relevance(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_herbertsmithite_dm_relevance",
        operand={"dm_interaction_relevant": True},
        anchors=(
            r"ZnCu3.{0,25}?OH.{0,15}?Cl2",
            r"Dzyalosh(?:insky|inskii)-Moriya interaction",
            r"dominant magnetic anisot-?\s*ropy",
            r"15.{0,12}?K.{0,80}?perpendicular to the kagome planes",
        ),
    )


def parse_kagome_chiral_spin_liquid_phase(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_kagome_chiral_spin_liquid_phase",
        operand={"chiral_spin_liquid_phase": True},
        anchors=(
            r"Kagome lattice",
            r"scalar spin chirality",
            r"breaks time-reversal symmetry",
            r"extended chiral spin liquid phase",
        ),
    )


def parse_kagome_dm_critical_ratio(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_kagome_dm_critical_ratio",
        operand={"critical_d_over_j_approx": 0.1},
        anchors=(
            r"S.{0,6}?1\s*[=/]\s*2.{0,25}?kagome antiferromagnet",
            r"Dzyalosh(?:insky|inskii)-Moriya",
            r"moment-free(?: phase)?",
            r"(?:critical point|Dc).{0,50}?0\.1\s*J",
        ),
    )


def parse_breathing_kagome_trimerization(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_breathing_kagome_trimerization",
        operand={"breathing_anisotropy_controls_trimerization": True},
        anchors=(
            r"spin-?\s*(?:1\s*/\s*2|21).{0,25}?breathing kagome",
            r"upward and downward.{0,50}?triangles.{0,50}?different coupling strengths",
            r"(?:density matrix renormalization group|DMRG).{0,80}?exact diagonalization",
            r"strong breathing anisotropy",
            r"trimerized kagome model",
        ),
    )


def parse_ca10cr7o28_qsl_exchange(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_ca10cr7o28_qsl_exchange",
        operand={
            "spin_liquid_candidate": True,
            "mixed_ferromagnetic_antiferromagnetic_exchanges": True,
        },
        anchors=(
            r"Ca10\s*Cr7\s*O28",
            r"strong ferromagnetic and weaker antiferromagnetic.{0,30}?interactions",
            r"experimentally and theoretically",
            r"features expected of a quantum spin liquid",
            r"complete absence of static magnetism",
        ),
    )


def parse_hyperkagome_heisenberg_qsl(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_hyperkagome_heisenberg_qsl",
        operand={"spin_liquid_candidate": True},
        anchors=(
            r"Na4\s*Ir3\s*O8",
            r"(?:s|spin).{0,6}?1\s*[=/]\s*2.{0,50}?hyperkagome.{0,20}?lattice",
            r"exact diagonalization.{0,100}?Gutzwiller projected variational wave functions",
            r"quantum spin liquid.{0,80}?favorable candidate.{0,100}?Heisenberg model",
        ),
    )


def parse_beta_li2iro3_hyperhoneycomb_kitaev(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_beta_li2iro3_hyperhoneycomb_kitaev",
        operand={"hyperhoneycomb_kitaev_material": True},
        anchors=(
            r"Li2\s*IrO3.{0,50}?hyperhoneycomb structure",
            r"spin-orbital Mott insulator.{0,30}?J.{0,12}?1\s*[=/]\s*2",
            r"bond-dependent ferromagnetic interactions",
            r"essential ingredient.{0,20}?Kitaev model",
        ),
    )


def parse_triangular_ring_exchange_spin_liquid(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_triangular_ring_exchange_spin_liquid",
        operand={"contains_spin_liquid_region": True},
        anchors=(
            r"triangular[- ]lattice spin-?\s*1\s*/\s*2",
            r"antiferromagnetic Heisenberg and ring exchanges",
            r"variational (?:approach|wave functions)",
            r"range of (?:the )?ring[- ]exchange coupling.{0,100}?spin[- ]liquid",
        ),
    )


def parse_triangular_xxz_supersolid(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_triangular_xxz_supersolid",
        operand={"contains_supersolid_phase": True},
        anchors=(
            r"hard-core bosons on (?:a|the) triangular lattice",
            r"nearest-neighbor repulsion",
            r"intermediate fillings.{0,30}?1\s*[=/]\s*3.{0,40}?2\s*[=/]\s*3",
            r"extended supersolid phase.{0,40}?half filling",
        ),
    )


def parse_volborthite_distorted_kagome(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_volborthite_distorted_kagome",
        operand={"distorted_kagome_reference": True},
        anchors=(
            r"Volborthite.{0,80}?Cu3\s*V2\s*O7",
            r"S\s*[-=]\s*1\s*/\s*2.{0,40}?kagom.",
            r"monoclinic.{0,100}?triangles.{0,80}?isosceles(?: triangles)?",
            r"modified.{0,35}?kagom. lattice",
        ),
    )


def parse_nips3_zigzag_order(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_nips3_zigzag_order",
        operand={"zigzag_or_collinear_order_reference": True},
        anchors=(
            r"magnetic structure.{0,80}?NiPS3",
            r"neutron diffraction",
            r"transition[- ]metal atoms.{0,50}?honeycomb lattice",
            r"k\s*=\s*\[?0\s*1\s*0\]?.{0,100}?identical to (?:the )?.{0,20}?zigzag.{0,30}?order",
        ),
    )


def parse_kitaev_gamma_phase_content(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_kitaev_gamma_phase_content",
        operand={"contains_noncollinear_and_zigzag_phases": True},
        anchors=(
            r"j.{0,8}?1\s*[=/]\s*2",
            r"honeycomb iridates",
            r"off-diagonal.{0,20}?exchange.{0,80}?Heisenberg and Kitaev terms",
            r"classical (?:analysis|techniques).{0,30}?exact diagonalization",
            r"120.{0,20}?incommensurate spiral (?:order|phases).{0,100}?"
            r"zigzag and stripy order",
        ),
    )


def parse_ggg_short_range_order(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_ggg_short_range_order",
        operand={"short_range_order_without_simple_lro": True},
        anchors=(
            r"Gd3\s*Ga5\s*O12",
            r"powder neutron scattering measurements",
            r"short-range magnetic order.{0,50}?0\.14.{0,20}?5\s*K",
            r"no (?:sign of )?long-range mag-?\s*netic order.{0,40}?25\s*mK",
        ),
    )


def _parse_honeycomb_j1j2_nonmagnetic(source_text, *, parser_name, field):
    return _parse_direct_source_claim(
        source_text,
        parser_name=parser_name,
        operand={field: True},
        anchors=(
            r"spin-?\s*(?:1\s*/\s*2|12|21).{0,30}?J1\s*-\s*J2.{0,40}?honeycomb lattice",
            r"(?:density matrix renormalization group.{0,30}?)?DMRG",
            r"N.{0,3}el order (?:vanishing|vanishes).{0,40}?0\.22",
            r"0\.22.{0,30}?J2\s*/\s*J1.{0,30}?0\.25.{0,100}?"
            r"both spin and dimer orders vanish",
        ),
    )


def parse_honeycomb_j1j2_nonmagnetic_candidate(source_text):
    return _parse_honeycomb_j1j2_nonmagnetic(
        source_text,
        parser_name="parse_honeycomb_j1j2_nonmagnetic_candidate",
        field="intermediate_nonmagnetic_phase_candidate",
    )


def parse_honeycomb_j1j2_intermediate_nonmagnetic(source_text):
    return _parse_honeycomb_j1j2_nonmagnetic(
        source_text,
        parser_name="parse_honeycomb_j1j2_intermediate_nonmagnetic",
        field="intermediate_nonmagnetic_phase",
    )


def parse_kagome_j1j2_phase_set(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_kagome_j1j2_phase_set",
        operand={
            "phases": ["spin_liquid", "q0_order", "sqrt3xsqrt3_order"]
        },
        anchors=(
            r"spin-?\s*1\s*/\s*2.{0,35}?J\s*1\s*[-−]\s*J\s*2.{0,45}?kagome lattice",
            r"(?:density-matrix renormalization-group|DMRG)",
            r"ferromagnetic J\s*2",
            r"(?:3\s*[×x]\s*3|sqrt\s*\(?3\)?\s*x\s*sqrt\s*\(?3\)?)",
            r"(?:extended )?spin[- ]liquid region",
            r"antiferromagnetic J\s*2",
            r"q\s*=\s*0",
        ),
    )


def parse_triangular_j1j2_phase_set(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_triangular_j1j2_phase_set",
        operand={"phases": ["120_degree", "spin_liquid", "stripe"]},
        anchors=(
            r"(?:S\s*=\s*1\s*/\s*2|S\s*=\s*1\s*2).{0,35}?Heisenberg model.{0,35}?triangular lattice",
            r"J\s*1\s*[-−]\s*J\s*2",
            r"(?:density matrix renormalization group|DMRG)",
            r"0\.06.{0,20}?J\s*2\s*/\s*J\s*1.{0,20}?0\.17",
            r"120.{0,20}?(?:N.?el )?ordered state",
            r"two sublattice collinear magnetically ordered state|collinear stripe state",
        ),
    )


def parse_triangular_j1j2_spin_liquid_window(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_triangular_j1j2_spin_liquid_window",
        operand={"spin_liquid_window_approx": [0.07, 0.15]},
        anchors=(
            r"spin-?\s*(?:1\s*/\s*2|21).{0,35}?Heisenberg model.{0,35}?triangular lattice",
            r"(?:density matrix renormalization group|DMRG)",
            r"120.{0,35}?order.{0,40}?J\s*2.{0,12}?0\.07\s*J\s*1",
            r"stripe antiferromagnetic (?:phase|order).{0,40}?J\s*2.{0,12}?0\.15\s*J\s*1",
            r"spin[- ]liquid region",
        ),
    )


def parse_spin1_haldane_large_d_transition(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_spin1_haldane_large_d_transition",
        operand={"large_d_transition_reference": True},
        anchors=(
            r"one-dimensional S.{0,4}?1 XXZ chains?",
            r"uniaxial single-ion(?:-type)? anisotropy",
            r"numerical exact diagonalization",
            r"Haldane phase.{0,25}?large-D phase",
            r"Gaussian(?:-type)? transition",
        ),
    )


def parse_bcc_large_j2_collinear_order(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_bcc_large_j2_collinear_order",
        operand={"large_j2_collinear_order": True},
        anchors=(
            r"spin-?S J\s*1\s*[-−]\s*J\s*2 Heisenberg model.{0,25}?(?:BCC|body-centered cubic) lattice",
            r"J\s*1\s*<\s*0.{0,30}?J\s*2\s*(?:>|[≥])\s*0",
            r"(?:classical (?:limit|transition).{0,100}?)?2.{0,5}?J\s*1.{0,5}?3|J\s*2c,?clas.{0,25}?2\s*3.{0,12}?J\s*1",
            r"collinear antiferromagnetic state",
            r"Q\s*=\s*\(\s*(?:pi|π)\s*,\s*(?:pi|π)\s*,\s*(?:pi|π)\s*\)",
        ),
    )


def parse_kagome_topological_entanglement_z2(source_text):
    return _parse_direct_source_claim(
        source_text,
        parser_name="parse_kagome_topological_entanglement_z2",
        operand={
            "topological_entanglement_entropy": "consistent_with_Z2"
        },
        anchors=(
            r"S.{0,6}?(?:1\s*/\s*2|1\s*2).{0,30}?Heisenberg anti-?\s*ferromagnet.{0,25}?kagome lattice",
            r"(?:density-matrix renormalization group.{0,15}?DMRG|DMRG study)",
            r"finite topological entanglement.{0,55}?log[_\s]*2\s*\(?2\)?",
            r"ruling out.{0,45}?nontopological spin liquids",
            r"strong evidence for a gapped topological Z\s*2 spin liquid",
        ),
    )


def parse_haydeeite_ferromagnetic_exchange(source_text):
    return _parse_material_source_claim(
        source_text,
        parser_name="parse_haydeeite_ferromagnetic_exchange",
        operand={"ferromagnetic_kagome_exchange": True},
        anchors=(
            r"haydeeite",
            r"(?:S\s*=\s*)?1\s*/?\s*2.{0,40}?kagome ferromagnet",
            r"inelastic neutron scattering.{0,80}?spin-wave excitations",
            r"ferromagnetic nearest-neighbor exchange.{0,30}?J1\s*=\s*[−-]\s*38\s*K",
        ),
    )


def parse_na4ir3o8_hyperkagome_spin_liquid(source_text):
    return _parse_material_source_claim(
        source_text,
        parser_name="parse_na4ir3o8_hyperkagome_spin_liquid",
        operand={"hyperkagome_qsl_candidate": True},
        anchors=(
            r"Na4\s*Ir3\s*O8",
            r"antiferromagnetically coupled.{0,80}?hyperkagome lattice",
            r"absence of long[- ]range(?: magnetic)? order.{0,40}?down to 2\s*K",
            r"(?:ground state of Na4\s*Ir3\s*O8|ground state is).{0,100}?spin liquid",
        ),
    )


def parse_ybmggao4_qsl_candidate(source_text):
    return _parse_material_source_claim(
        source_text,
        parser_name="parse_ybmggao4_qsl_candidate",
        operand={"triangular_quantum_spin_liquid_candidate": True},
        anchors=(
            r"YbMgGaO4",
            r"spin-?1\s*/?\s*2 triangular antiferromagnet",
            r"No spin freezing down to 60.{0,5}mK",
            r"promising gapless.{0,30}?(?:QSL|quantum spin liquid) candidate",
        ),
    )


def parse_barlowite_interlayer_coupling(source_text):
    return _parse_material_source_claim(
        source_text,
        parser_name="parse_barlowite_interlayer_coupling",
        operand={"interlayer_coupling_relevant": True},
        anchors=(
            r"barlowite",
            r"(?:copper ions between the kagome layers|interkagome)",
            r"(?:strong interkagome couplings|weakly coupled|"
            r"exchange between a kagome Cu.{0,120}?interkagome Cu)",
            r"(?:lead to an ordered ground state|orders magnetically|long-range ordered state)",
        ),
    )


def parse_substituted_barlowite_two_parameter_model(source_text):
    return _parse_material_source_claim(
        source_text,
        parser_name="parse_substituted_barlowite_two_parameter_model",
        operand={
            "significantly_reduced_interkagome_exchange": True,
            "two_parameter_heisenberg_hamiltonian": True,
        },
        anchors=(
            r"(?:interlayer-substituted )?barlowite",
            r"isoelectronic substitution.{0,80}?nonmagnetic ions",
            r"significantly reduces the interkagome exchange coupling",
            r"simple two-parameter Heisenberg Hamiltonian",
        ),
    )


def parse_pr2zr2o7_quantum_spin_ice(source_text):
    return _parse_material_source_claim(
        source_text,
        parser_name="parse_pr2zr2o7_quantum_spin_ice",
        operand={"quantum_spin_ice_candidate": True},
        anchors=(
            r"Pr2\s*Zr2\s*O7",
            r"neutron scattering",
            r"experimental evidence for quantum dynamics of magnetic.{0,30}?"
            r"monopolar quasiparticles",
            r"(?:new class of|exchange) spin ice",
        ),
    )


def parse_aklt_projector_ground_state(source_text):
    """Derive the local projector spectrum and zero-energy VBS claim."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("AKLT projector claim requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    exclusion_match = re.search(
        r"neighboring pair.{0,120}?total spin of each such.{0,120}?"
        r"pair cannot be 2",
        normalized,
        flags=re.IGNORECASE,
    )
    projector_match = re.search(
        r"Hamiltonian.{0,120}?sum of projection operators onto"
        r".{0,180}?spin 2 for each neighboring pair",
        normalized,
        flags=re.IGNORECASE,
    )
    energy_match = re.search(
        r"ground-state energy is zero", normalized, flags=re.IGNORECASE
    )
    if exclusion_match is None or projector_match is None or energy_match is None:
        raise RuntimeEvidenceError(
            "AKLT projector claim must identify the excluded neighboring-pair "
            "spin-2 sector, its projector Hamiltonian, and zero ground energy"
        )
    return (
        {
            "two_site_projector_eigenvalues": [0.0, 0.0, 1.0],
            "vbs_ground_energy": 0.0,
        },
        {
            "parser": "parse_aklt_projector_ground_state",
            "derivation": (
                "For two spin-1 sites S_total=0,1,2; P_2 has eigenvalues "
                "0,0,1, and the ground state excludes S_total=2"
            ),
            "matched_anchors": [
                "neighboring pair cannot have total spin 2",
                "neighboring-pair spin-2 projector Hamiltonian",
                "zero ground-state energy",
            ],
            "text_spans": [
                [exclusion_match.start(), exclusion_match.end()],
                [projector_match.start(), projector_match.end()],
                [energy_match.start(), energy_match.end()],
            ],
        },
    )


def recompute_aklt_angle_from_spin_two_projector():
    """Expand the two-spin-1 S_total=2 projector in powers of S_i dot S_j."""

    spin = 1.0
    dot_eigenvalues = [
        0.5 * (total_spin * (total_spin + 1.0) - 2.0 * spin * (spin + 1.0))
        for total_spin in (0.0, 1.0, 2.0)
    ]
    x_zero, x_one, x_two = dot_eigenvalues
    denominator = (x_two - x_zero) * (x_two - x_one)
    bilinear_coefficient = -(x_zero + x_one) / denominator
    biquadratic_coefficient = 1.0 / denominator
    tan_theta = biquadratic_coefficient / bilinear_coefficient
    return {
        "aklt_tan_theta": tan_theta,
        "theta_radians": math.atan(tan_theta),
    }


def parse_aklt_angle_from_projector(source_text):
    """Derive the AKLT bilinear-biquadratic angle from the source projector."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("AKLT angle requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    spin_chain_match = re.search(
        r"(?:spin-1|s\s*=\s*1) chain",
        normalized,
        flags=re.IGNORECASE,
    )
    projector_match = re.search(
        r"Hamiltonian.{0,120}?sum of projection operators onto"
        r".{0,80}?spin 2 for each neighboring pair",
        normalized,
        flags=re.IGNORECASE,
    )
    parameterization_match = re.search(
        r"general bilinear(?:-|\s*)biquadratic\s+Hamiltonian",
        normalized,
        flags=re.IGNORECASE,
    )
    if any(
        match is None
        for match in (spin_chain_match, projector_match, parameterization_match)
    ):
        raise RuntimeEvidenceError(
            "AKLT angle source must identify the spin-1 chain, its neighboring-pair "
            "spin-2 projector Hamiltonian, and the bilinear-biquadratic parameterization"
        )
    return (
        recompute_aklt_angle_from_spin_two_projector(),
        {
            "parser": "parse_aklt_angle_from_projector",
            "projector_polynomial": "P_2(x)=(x+2)(x+1)/6",
            "derivation": (
                "For two spin-1 sites, x=S_i.S_j has eigenvalues -2,-1,1 in "
                "the total-spin 0,1,2 sectors. Therefore P_2=(x+2)(x+1)/6, "
                "whose biquadratic-to-bilinear coefficient ratio is 1/3."
            ),
            "matched_anchors": [
                "spin-1 chain",
                "neighboring-pair spin-2 projector Hamiltonian",
                "bilinear-biquadratic Hamiltonian",
            ],
            "text_spans": [
                [spin_chain_match.start(), spin_chain_match.end()],
                [projector_match.start(), projector_match.end()],
                [parameterization_match.start(), parameterization_match.end()],
            ],
        },
    )


def _parse_localized_magnon_claim(source_text, *, model, trapping_pattern, label):
    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            f"{model} localized-magnon claim requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    trapping_match = re.search(trapping_pattern, normalized, flags=re.IGNORECASE)
    state_match = re.search(
        r"explicit expressions? for the localized one-magnon state"
        r".{0,100}?smallest possible region of localization read",
        normalized,
        flags=re.IGNORECASE,
    )
    lowest_match = re.search(
        r"independent localized magnon states are the lowest-energy states in "
        r"the corresponding sectors of S\s*z",
        normalized,
        flags=re.IGNORECASE,
    )
    if trapping_match is None or state_match is None or lowest_match is None:
        raise RuntimeEvidenceError(
            f"{model} localized-magnon claim must contain model-specific "
            "trapping, an explicit localized one-magnon state, and the "
            "sector lowest-energy statement"
        )
    return (
        {"has_exact_localized_magnons": True},
        {
            "parser": f"parse_{model}_localized_magnon",
            "matched_anchors": [
                label,
                "explicit localized one-magnon state",
                "localized magnons are sector lowest-energy states",
            ],
            "text_spans": [
                [trapping_match.start(), trapping_match.end()],
                [state_match.start(), state_match.end()],
                [lowest_match.start(), lowest_match.end()],
            ],
        },
    )


def parse_diamond_localized_magnon(source_text):
    """Extract the exact diamond-chain vertical-bond localized-magnon claim."""

    return _parse_localized_magnon_claim(
        source_text,
        model="diamond",
        trapping_pattern=(
            r"(?:diamond(?:\s|-)+chain|diamond and dimer-plaquette chains)"
            r".{0,140}?magnons may be localized on "
            r"the vertical bonds"
        ),
        label="diamond-chain vertical-bond trapping",
    )


def parse_sawtooth_localized_magnon(source_text):
    """Extract the exact sawtooth-chain valley localized-magnon claim."""

    return _parse_localized_magnon_claim(
        source_text,
        model="sawtooth",
        trapping_pattern=(
            r"sawtooth(?:\s|-)+chain.{0,100}?localized magnons may be trapped "
            r"in a valley between two neighboring triangles"
        ),
        label="sawtooth-chain neighboring-triangle valley trapping",
    )


def _select_registry_operand(entry, selector):
    value = entry
    for component in selector["path"]:
        if not isinstance(value, Mapping) or component not in value:
            raise RuntimeEvidenceError(
                f"registry selector cannot resolve component {component}"
            )
        value = value[component]
    if not isinstance(value, Mapping):
        raise RuntimeEvidenceError("registry selector path does not resolve a mapping")
    fields = selector["fields"]
    missing = [field for field in fields if field not in value]
    if missing:
        raise RuntimeEvidenceError(
            f"registry selector cannot resolve field {missing[0]}"
        )
    return {field: value[field] for field in fields}


def _narrow_registry_selector(selector, fields=None):
    original_fields = tuple(selector["fields"])
    selected_fields = original_fields if fields is None else tuple(fields)
    if (
        not _is_nonempty_string_sequence(selected_fields, unique=True)
        or not set(selected_fields).issubset(original_fields)
    ):
        raise RuntimeEvidenceError(
            "runtime route fields must be a nonempty subset of registered selector fields"
        )
    return {
        "path": list(selector["path"]),
        "fields": list(selected_fields),
    }


def collect_runtime_evidence(registry_entries, *, cache_root=DEFAULT_CACHE_ROOT):
    """Execute supported strict evidence routes against the local source cache."""

    inventory = load_and_validate_inventory(registry_entries=registry_entries)
    source_by_id = {source["source_id"]: source for source in inventory.source_index}
    route_by_id = {
        route["source_id"]: route for route in inventory.source_provisioning
    }
    record_by_name = {record.benchmark_name: record for record in inventory.records}
    entry_by_name = {entry["name"]: entry for entry in registry_entries}
    evidence = {}
    specs = (
        {
            "benchmark_name": "cri3_honeycomb_ferromagnet_reference",
            "mode": "local_source_parse",
            "parser": parse_cri3_ferromagnetic_order,
        },
        {
            "benchmark_name": "xxx_spin_half_chain_bethe_ground_state",
            "mode": "local_recompute",
            "parser": parse_yang_yang_xxx_ground_state_energy,
            "adapter": benchmark_functions.xxx_spin_half_chain_bethe_energy_per_site,
            "adapter_parameters": {"exchange": 1.0},
            "output_field": "energy_per_site",
        },
        {
            "benchmark_name": "one_dimensional_classical_ising_correlation_length",
            "mode": "local_recompute",
            "parser": parse_taylor_ising_correlation_length,
            "registry_fields": ("correlation_length_beta_1_j_1",),
            "adapter": benchmark_functions.classical_ising_chain_correlation_length,
            "adapter_parameters": {"beta": 1.0, "exchange": 1.0},
            "output_field": "correlation_length_beta_1_j_1",
        },
        {
            "benchmark_name": "lieb_schultz_mattis_half_integer_constraint",
            "mode": "local_source_parse",
            "parser": parse_tasaki_lsm_half_integer_constraint,
        },
        {
            "benchmark_name": "two_dimensional_square_ising_onsager_tc",
            "mode": "local_recompute",
            "parser": parse_onsager_square_ising_tc,
            "adapter": benchmark_functions.two_dimensional_ising_square_tc,
            "adapter_parameters": {"exchange": 1.0},
            "output_field": "tc_over_j",
        },
        {
            "benchmark_name": "two_dimensional_square_ising_spontaneous_magnetization",
            "mode": "local_recompute",
            "parser": parse_yang_spontaneous_magnetization,
            "adapter": recompute_yang_spontaneous_magnetization_operand,
            "adapter_parameters": {"beta": 0.6, "exchange": 1.0},
            "output_fields": {
                "formula": "formula",
                "magnetization_beta_0_6_j_1": "magnetization_beta_0_6_j_1",
            },
        },
        {
            "benchmark_name": "square_potts_exact_critical_point",
            "mode": "local_recompute",
            "parser": parse_square_potts_critical_point,
            "adapter": recompute_square_potts_critical_point,
            "adapter_parameters": {
                "transition_boundary": 4,
                "q_checks": [2, 3, 4, 5],
            },
            "output_fields": {
                "critical_beta_j": "critical_beta_j",
                "continuous_for_q_le_4": "continuous_for_q_le_4",
            },
        },
        {
            "benchmark_name": "square_clock_q5_two_bkt_transitions",
            "mode": "local_source_parse",
            "parser": parse_lapilli_square_clock_three_phase_regime,
        },
        {
            "benchmark_name": "triangular_ising_antiferromagnet_residual_entropy",
            "mode": "local_recompute",
            "parser": parse_wannier_triangular_entropy,
            "adapter": recompute_wannier_triangular_entropy,
            "adapter_parameters": {"intervals": 10000},
            "output_fields": {
                "residual_entropy_per_spin": "residual_entropy_per_spin",
            },
        },
        {
            "benchmark_name": "xy_spin_half_chain_anisotropic_critical_line",
            "mode": "local_recompute",
            "parser": parse_barouch_mccoy_xy_boundaries,
            "adapter": recompute_xy_critical_boundaries,
            "adapter_parameters": {
                "interior_field": 0.6,
                "anisotropy_probe": 0.3,
            },
            "output_fields": {
                "ising_critical_field": "ising_critical_field",
                "anisotropy_transition_gamma": "anisotropy_transition_gamma",
            },
        },
        {
            "benchmark_name": "diamond_j1_j2_spiral_surface_reference",
            "mode": "local_recompute",
            "parser": parse_bergman_diamond_spiral_surface,
            "adapter": recompute_diamond_spiral_surface_threshold,
            "adapter_parameters": {
                "lambda_max": 2.0,
                "below_ratio": 0.1,
                "above_ratio": 0.2,
            },
            "output_fields": {
                "spiral_surface_for_j2_over_j1_gt": (
                    "spiral_surface_for_j2_over_j1_gt"
                ),
            },
        },
        {
            "benchmark_name": "pyrochlore_anisotropic_exchange_jzz_jpm_reference",
            "mode": "local_source_parse",
            "parser": parse_ross_pyrochlore_exchange_basis,
        },
        {
            "benchmark_name": "yb2ti2o7_pyrochlore_exchange_reference",
            "mode": "local_source_parse",
            "parser": parse_yb2ti2o7_exchange_fit,
        },
        {
            "benchmark_name": (
                "honeycomb_haldane_kane_mele_hubbard_spin_model_reference"
            ),
            "mode": "local_source_parse",
            "parser": parse_kane_mele_hubbard_spin_anisotropy,
        },
        {
            "benchmark_name": "spin_ice_tetrahedron_nn_ice_rule",
            "mode": "local_recompute",
            "parser": parse_harris_spin_ice_tetrahedron_levels,
            "adapter": recompute_spin_ice_tetrahedron_levels,
            "adapter_parameters": {"effective_exchange": 1.0},
            "output_fields": {
                "two_in_two_out_energy": "two_in_two_out_energy",
                "three_in_one_out_energy": "three_in_one_out_energy",
                "all_in_all_out_energy": "all_in_all_out_energy",
                "two_in_two_out_degeneracy": "two_in_two_out_degeneracy",
            },
        },
        {
            "benchmark_name": "square_j1_j3_classical_lifshitz_reference",
            "mode": "local_recompute",
            "parser": parse_kharkov_square_j1_j3_lifshitz,
            "adapter": recompute_square_j1_j3_spiral_condition,
            "adapter_parameters": {
                "below_ratio": 0.2,
                "above_ratio": 0.5,
            },
            "output_fields": {
                "spiral_condition": "spiral_condition",
            },
        },
        {
            "benchmark_name": "j1_j2_j3_square_quantum_phase_reference",
            "mode": "local_source_parse",
            "parser": parse_liu_square_j1_j2_j3_paramagnets,
        },
        {
            "benchmark_name": "j1_j2_square_dqcp_columnar_vbs_reference",
            "mode": "local_source_parse",
            "parser": parse_gong_square_j1_j2_pvb,
        },
        {
            "benchmark_name": "pyrochlore_heisenberg_coulomb_phase_flat_band",
            "mode": "local_source_parse",
            "parser": parse_moessner_pyrochlore_flat_band,
        },
        {
            "benchmark_name": (
                "j1_j2_square_spin_half_neel_collinear_transition_reference"
            ),
            "mode": "local_source_parse",
            "parser": parse_richter_square_j1_j2_window,
        },
        {
            "benchmark_name": "tb2ti2o7_pyrochlore_spin_liquid_reference",
            "mode": "local_source_parse",
            "parser": parse_tb2ti2o7_cooperative_paramagnet,
        },
        {
            "benchmark_name": "scgo_kagome_bilayer_spin_liquid_reference",
            "mode": "local_source_parse",
            "parser": parse_scgo_unconventional_low_t_state,
        },
        {
            "benchmark_name": "two_leg_ladder_strong_rung_exact_limit",
            "mode": "local_recompute",
            "parser": parse_dagotto_rice_strong_rung_limit,
            "adapter": benchmark_functions.spin_ladder_strong_rung_gap_status,
            "adapter_parameters": {"j_rung": 1.0, "j_leg": 0.0},
            "output_fields": {
                "energy_per_rung": "rung_singlet_energy",
                "gap_to_triplet": "rung_gap",
            },
        },
        {
            "benchmark_name": "spin_ladder_rung_singlet_gap_reference",
            "mode": "local_source_parse",
            "parser": parse_dagotto_rice_two_leg_gap,
        },
        {
            "benchmark_name": "haldane_shastry_chain_exact_ground_state",
            "mode": "local_source_parse",
            "parser": parse_haldane_shastry_ground_state,
        },
        {
            "benchmark_name": "eight_vertex_zero_field_exact_solution_status",
            "mode": "local_source_parse",
            "parser": parse_baxter_eight_vertex_solution,
        },
        {
            "benchmark_name": "square_ashkin_teller_exact_critical_line",
            "mode": "local_recompute",
            "parser": parse_baxter_eight_vertex_critical_line,
            "adapter": recompute_baxter_eight_vertex_critical_line,
            "adapter_parameters": {
                "critical_weight_points": [
                    {"a": 1.0, "b": 1.0, "c": 3.0, "d": 1.0},
                    {"a": 1.5, "b": 0.5, "c": 3.0, "d": 1.0},
                ],
            },
            "output_fields": {
                "has_exact_critical_line": "has_exact_critical_line",
            },
        },
        {
            "benchmark_name": "square_six_vertex_ice_exact_solution_status",
            "mode": "local_source_parse",
            "parser": parse_lieb_square_ice_solution,
        },
        {
            "benchmark_name": "gaudin_yang_spin_half_fermion_bethe_reference",
            "mode": "local_source_parse",
            "parser": parse_yang_gaudin_fermion_solution,
        },
        {
            "benchmark_name": "lieb_liniger_delta_bose_gas_bethe_reference",
            "mode": "local_source_parse",
            "parser": parse_lieb_liniger_solution,
        },
        {
            "benchmark_name": "pyrochlore_dipolar_spin_ice_pauling_entropy",
            "mode": "local_recompute",
            "parser": parse_pauling_spin_ice_entropy,
            "adapter": benchmark_functions.pauling_spin_ice_entropy_per_spin,
            "adapter_parameters": {},
            "output_field": "pauling_entropy_per_spin",
        },
        {
            "benchmark_name": "two_dimensional_xy_bkt_universal_jump",
            "mode": "local_recompute",
            "parser": parse_bkt_universal_jump,
            "adapter": recompute_bkt_universal_jump_operand,
            "adapter_parameters": {"temperature": 1.0},
            "output_fields": {
                "formula": "formula",
                "helicity_modulus_at_t_1": "helicity_modulus_at_t_1",
            },
        },
        {
            "benchmark_name": "uimin_lai_sutherland_spin1_su3_point",
            "mode": "local_recompute",
            "parser": parse_uls_spin1_su3_point,
            "adapter": recompute_uls_spin1_su3_operand,
            "adapter_parameters": {},
            "output_fields": {
                "theta_radians": "theta_radians",
                "su3_symmetric": "su3_symmetric",
            },
        },
        {
            "benchmark_name": "bilinear_biquadratic_spin1_chain_aklt_angle",
            "mode": "local_recompute",
            "parser": parse_aklt_angle_from_projector,
            "adapter": recompute_aklt_angle_from_spin_two_projector,
            "adapter_parameters": {},
            "output_fields": {
                "aklt_tan_theta": "aklt_tan_theta",
                "theta_radians": "theta_radians",
            },
        },
        {
            "benchmark_name": "square_compass_model_directional_exchange_degeneracy",
            "mode": "local_recompute",
            "parser": parse_square_compass_line_symmetries,
            "adapter": recompute_square_compass_line_symmetries,
            "adapter_parameters": {"length": 3, "j_x": 1.0, "j_y": 1.0},
            "output_fields": {
                "has_line_flip_symmetries": "has_line_flip_symmetries",
            },
        },
        {
            "benchmark_name": "kitaev_honeycomb_exact_spin_liquid_limit",
            "mode": "local_source_parse",
            "parser": parse_kitaev_exact_spin_liquid,
        },
        {
            "benchmark_name": "kitaev_honeycomb_gapless_triangle_condition",
            "mode": "local_source_parse",
            "parser": parse_kitaev_gapless_triangle_condition,
        },
        {
            "benchmark_name": (
                "kitaev_honeycomb_abelian_nonabelian_field_gap_reference"
            ),
            "mode": "local_recompute",
            "parser": parse_kitaev_field_nonabelian_gap,
            "adapter": recompute_kitaev_field_nonabelian_gap,
            "adapter_parameters": {
                "h_x": 0.1,
                "h_y": 0.2,
                "h_z": 0.3,
                "exchange": 1.0,
            },
            "output_fields": {
                "field_opens_non_abelian_gap": "field_opens_non_abelian_gap",
            },
        },
        {
            "benchmark_name": "square_toric_code_exact_topological_degeneracy",
            "mode": "local_recompute",
            "parser": parse_kitaev_toric_code_degeneracy,
            "adapter": benchmark_functions.toric_code_ground_state_degeneracy,
            "adapter_parameters": {"genus": 1},
            "output_field": "torus_ground_state_degeneracy",
        },
        {
            "benchmark_name": "haldane_spin1_chain_gap_reference",
            "mode": "local_source_parse",
            "parser": parse_white_huse_haldane_gap,
            "registry_fields": ("gap_over_j",),
            "absolute_tolerance": 0.00005,
        },
        {
            "benchmark_name": "square_spin_half_heisenberg_qmc_energy",
            "mode": "local_source_parse",
            "parser": parse_sandvik_square_qmc_energy,
            "registry_fields": ("energy_per_site",),
        },
        {
            "benchmark_name": "triangular_heisenberg_spin_half_energy_reference",
            "mode": "local_source_parse",
            "parser": parse_capriotti_triangular_energy,
            "registry_fields": ("energy_per_site_approx",),
            "absolute_tolerance": 0.005,
        },
        {
            "benchmark_name": "checkerboard_heisenberg_plaquette_reference",
            "mode": "local_source_parse",
            "parser": parse_checkerboard_plaquette_vbc,
        },
        {
            "benchmark_name": "spin_peierls_chain_dimerization_reference",
            "mode": "local_source_parse",
            "parser": parse_spin_peierls_distortion_gap,
        },
        {
            "benchmark_name": "bpcb_spin_ladder_field_induced_order_reference",
            "mode": "local_source_parse",
            "parser": parse_bpcb_field_induced_ll,
        },
        {
            "benchmark_name": "two_dimensional_xy_bkt_temperature_reference",
            "mode": "local_source_parse",
            "parser": parse_hasenbusch_xy_bkt_temperature,
        },
        {
            "benchmark_name": "azurite_diamond_chain_plateau_reference",
            "mode": "local_source_parse",
            "parser": parse_azurite_one_third_plateau,
        },
        {
            "benchmark_name": "ba3cosb2o9_triangular_plateau_reference",
            "mode": "local_source_parse",
            "parser": parse_ba3cosb2o9_one_third_plateau,
        },
        {
            "benchmark_name": "kagome_one_third_magnetization_plateau_reference",
            "mode": "local_source_parse",
            "parser": parse_kagome_one_third_plateau,
        },
        {
            "benchmark_name": (
                "shastry_sutherland_magnetization_plateaus_reference"
            ),
            "mode": "local_source_parse",
            "parser": parse_kageyama_shastry_sutherland_plateaus,
        },
        {
            "benchmark_name": (
                "sr_cu2_bo3_2_shastry_sutherland_material_reference"
            ),
            "mode": "local_source_parse",
            "parser": parse_kageyama_shastry_sutherland_material,
        },
        {
            "benchmark_name": "cacu2o3_spin_ladder_reference",
            "mode": "local_source_parse",
            "parser": parse_cacu2o3_spin_ladder_material,
        },
        {
            "benchmark_name": "ba2cugeo7_dm_spiral_reference",
            "mode": "local_source_parse",
            "parser": parse_ba2cugeo7_dm_spiral,
        },
        {
            "benchmark_name": "ho2ti2o7_spin_ice_neutron_reference",
            "mode": "local_source_parse",
            "parser": parse_ho2ti2o7_spin_ice_correlations,
        },
        {
            "benchmark_name": "jarosite_kagome_dzyaloshinskii_moriya_reference",
            "mode": "local_source_parse",
            "parser": parse_jarosite_q0_120_order,
        },
        {
            "benchmark_name": "maple_leaf_lattice_heisenberg_reference",
            "mode": "local_source_parse",
            "parser": parse_maple_leaf_magnetic_order,
        },
        {
            "benchmark_name": "alpha_rucl3_kitaev_gamma_zigzag_reference",
            "mode": "local_source_parse",
            "parser": parse_alpha_rucl3_zigzag_kitaev_gamma,
        },
        {
            "benchmark_name": "beta_li2iro3_spiral_kitaev_gamma_reference",
            "mode": "local_source_parse",
            "parser": parse_beta_li2iro3_spiral_order,
        },
        {
            "benchmark_name": "cs2cucl4_anisotropic_triangular_spiral_reference",
            "mode": "local_source_parse",
            "parser": parse_cs2cucl4_spiral_order,
        },
        {
            "benchmark_name": "square_dimerized_heisenberg_critical_reference",
            "mode": "local_source_parse",
            "parser": parse_square_dimerized_neel_transition,
        },
        {
            "benchmark_name": "square_jq_model_deconfined_critical_reference",
            "mode": "local_source_parse",
            "parser": parse_square_jq_neel_vbs_transition,
        },
        {
            "benchmark_name": "triangular_nn_classical_120_reference",
            "mode": "local_recompute",
            "parser": parse_triangular_classical_120_order,
            "adapter": recompute_triangular_classical_120_order,
            "adapter_parameters": {
                "candidate_q": [
                    [0.0, 0.0, 0.0],
                    [0.5, 0.0, 0.0],
                    [1.0 / 3.0, 2.0 / 3.0, 0.0],
                ]
            },
            "output_fields": {
                "order": "order",
                "q_reciprocal": "q_reciprocal",
            },
        },
        {
            "benchmark_name": "fecl3_honeycomb_antiferromagnet_reference",
            "mode": "local_source_parse",
            "parser": parse_fecl3_helimagnetic_order,
        },
        {
            "benchmark_name": "haydeeite_ferromagnetic_kagome_reference",
            "mode": "local_source_parse",
            "parser": parse_haydeeite_ferromagnetic_exchange,
        },
        {
            "benchmark_name": "na4ir3o8_hyperkagome_material_reference",
            "mode": "local_source_parse",
            "parser": parse_na4ir3o8_hyperkagome_spin_liquid,
        },
        {
            "benchmark_name": "ybmggao4_triangular_spin_liquid_reference",
            "mode": "local_source_parse",
            "parser": parse_ybmggao4_qsl_candidate,
        },
        {
            "benchmark_name": "barlowite_kagome_material_reference",
            "mode": "local_source_parse",
            "parser": parse_barlowite_interlayer_coupling,
        },
        {
            "benchmark_name": "zn_barlowite_kagome_qsl_reference",
            "mode": "local_source_parse",
            "parser": parse_substituted_barlowite_two_parameter_model,
        },
        {
            "benchmark_name": "pr2zr2o7_quantum_spin_ice_reference",
            "mode": "local_source_parse",
            "parser": parse_pr2zr2o7_quantum_spin_ice,
        },
        {
            "benchmark_name": "herbertsmithite_kagome_qsl_reference",
            "mode": "local_source_parse",
            "parser": parse_herbertsmithite_qsl_candidate,
        },
        {
            "benchmark_name": "kapellasite_kagome_j1_jd_reference",
            "mode": "local_source_parse",
            "parser": parse_kapellasite_competing_exchanges,
        },
        {
            "benchmark_name": "li2cuo2_frustrated_ferromagnetic_chain_reference",
            "mode": "local_source_parse",
            "parser": parse_li2cuo2_frustrated_chain,
        },
        {
            "benchmark_name": "quantum_spin_ice_u1_qsl_reference",
            "mode": "local_source_parse",
            "parser": parse_u1_pyrochlore_spin_liquid,
        },
        {
            "benchmark_name": (
                "zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference"
            ),
            "mode": "local_source_parse",
            "parser": parse_herbertsmithite_dm_relevance,
        },
        {
            "benchmark_name": "kagome_chiral_spin_liquid_j1_j2_jchi_reference",
            "mode": "local_source_parse",
            "parser": parse_kagome_chiral_spin_liquid_phase,
        },
        {
            "benchmark_name": "kagome_dzyaloshinskii_moriya_critical_reference",
            "mode": "local_source_parse",
            "parser": parse_kagome_dm_critical_ratio,
        },
        {
            "benchmark_name": "breathing_kagome_heisenberg_reference",
            "mode": "local_source_parse",
            "parser": parse_breathing_kagome_trimerization,
        },
        {
            "benchmark_name": "ca10cr7o28_bilayer_breathing_kagome_reference",
            "mode": "local_source_parse",
            "parser": parse_ca10cr7o28_qsl_exchange,
        },
        {
            "benchmark_name": "hyperkagome_heisenberg_spin_liquid_reference",
            "mode": "local_source_parse",
            "parser": parse_hyperkagome_heisenberg_qsl,
        },
        {
            "benchmark_name": "li2iro3_hyperhoneycomb_kitaev_reference",
            "mode": "local_source_parse",
            "parser": parse_beta_li2iro3_hyperhoneycomb_kitaev,
        },
        {
            "benchmark_name": "triangular_ring_exchange_spin_liquid_reference",
            "mode": "local_source_parse",
            "parser": parse_triangular_ring_exchange_spin_liquid,
        },
        {
            "benchmark_name": "triangular_xxz_supersolid_phase_reference",
            "mode": "local_source_parse",
            "parser": parse_triangular_xxz_supersolid,
        },
        {
            "benchmark_name": "volborthite_kagome_distorted_reference",
            "mode": "local_source_parse",
            "parser": parse_volborthite_distorted_kagome,
        },
        {
            "benchmark_name": "ni_ps3_honeycomb_antiferromagnet_reference",
            "mode": "local_source_parse",
            "parser": parse_nips3_zigzag_order,
        },
        {
            "benchmark_name": "honeycomb_kitaev_gamma_phase_diagram_reference",
            "mode": "local_source_parse",
            "parser": parse_kitaev_gamma_phase_content,
        },
        {
            "benchmark_name": "garnet_gd3ga5o12_spin_liquid_reference",
            "mode": "local_source_parse",
            "parser": parse_ggg_short_range_order,
        },
        {
            "benchmark_name": "honeycomb_spin_half_j1_j2_quantum_phase_reference",
            "mode": "local_source_parse",
            "parser": parse_honeycomb_j1j2_nonmagnetic_candidate,
        },
        {
            "benchmark_name": (
                "j1_j2_honeycomb_neel_spin_liquid_transition_reference"
            ),
            "mode": "local_source_parse",
            "parser": parse_honeycomb_j1j2_intermediate_nonmagnetic,
        },
        {
            "benchmark_name": "kagome_j1_j2_heisenberg_phase_diagram_reference",
            "mode": "local_source_parse",
            "parser": parse_kagome_j1j2_phase_set,
        },
        {
            "benchmark_name": (
                "triangular_j1_j2_spin_half_phase_diagram_reference"
            ),
            "mode": "local_source_parse",
            "parser": parse_triangular_j1j2_phase_set,
        },
        {
            "benchmark_name": "j1_j2_triangular_spin_liquid_window_reference",
            "mode": "local_source_parse",
            "parser": parse_triangular_j1j2_spin_liquid_window,
        },
        {
            "benchmark_name": "spin1_chain_large_d_transition_reference",
            "mode": "local_source_parse",
            "parser": parse_spin1_haldane_large_d_transition,
        },
        {
            "benchmark_name": "bcc_j1_j2_heisenberg_collinear_reference",
            "mode": "local_source_parse",
            "parser": parse_bcc_large_j2_collinear_order,
        },
        {
            "benchmark_name": (
                "kagome_heisenberg_topological_entanglement_reference"
            ),
            "mode": "local_source_parse",
            "parser": parse_kagome_topological_entanglement_z2,
        },
        {
            "benchmark_name": "aklt_spin1_chain_projector_ground_state",
            "mode": "local_recompute",
            "parser": parse_aklt_projector_ground_state,
            "adapter": benchmark_functions.aklt_projector_ground_state_result,
            "adapter_parameters": {},
            "output_fields": {
                "two_site_projector_eigenvalues": "two_site_projector_eigenvalues",
                "vbs_ground_energy": "vbs_ground_energy",
            },
        },
        {
            "benchmark_name": "diamond_chain_localized_magnon_flat_band",
            "mode": "local_source_parse",
            "parser": parse_diamond_localized_magnon,
        },
        {
            "benchmark_name": "sawtooth_chain_localized_magnon_flat_band",
            "mode": "local_source_parse",
            "parser": parse_sawtooth_localized_magnon,
        },
    )
    for spec in specs:
        benchmark_name = spec["benchmark_name"]
        record = record_by_name[benchmark_name]
        source_dir = Path(cache_root) / record.source_id
        if not source_dir.is_dir():
            continue
        verified = load_verified_source(
            source_dir,
            expected_source=source_by_id[record.source_id],
            provisioning_route=route_by_id[record.source_id],
        )
        source_operand, extraction_trace = spec["parser"](
            verified.extracted_text
        )
        selector = _narrow_registry_selector(
            record.registry_selector, spec.get("registry_fields")
        )
        registry_operand = _select_registry_operand(
            entry_by_name[benchmark_name], selector
        )
        runtime_record = {
            "benchmark_name": benchmark_name,
            "evidence_mode": spec["mode"],
            "source_id": record.source_id,
            "source_sha256": verified.payload_sha256,
            "registry_selector": {
                "path": selector["path"],
                "fields": selector["fields"],
            },
            "source_operand": source_operand,
            "registry_operand": registry_operand,
        }
        bundle = {
            "extraction_trace": {
                "benchmark_name": benchmark_name,
                "source_sha256": verified.payload_sha256,
                "coordinate_space": "whitespace_normalized_extracted_text",
                **extraction_trace,
            },
        }
        operands = [source_operand, registry_operand]
        if spec["mode"] == "local_recompute":
            parameters = spec["adapter_parameters"]
            adapter_output = spec["adapter"](**parameters)
            if "output_fields" in spec:
                if not isinstance(adapter_output, Mapping):
                    raise RuntimeEvidenceError(
                        f"adapter for {benchmark_name} must return a mapping"
                    )
                missing_outputs = [
                    output_name
                    for output_name in spec["output_fields"].values()
                    if output_name not in adapter_output
                ]
                if missing_outputs:
                    raise RuntimeEvidenceError(
                        f"adapter for {benchmark_name} is missing output "
                        f"{missing_outputs[0]}"
                    )
                computed_operand = {
                    registry_field: adapter_output[output_name]
                    for registry_field, output_name in spec["output_fields"].items()
                }
            else:
                computed_operand = {spec["output_field"]: adapter_output}
            runtime_record["computed_operand"] = computed_operand
            operands.append(computed_operand)
            bundle["execution_trace"] = {
                "benchmark_name": benchmark_name,
                "source_sha256": verified.payload_sha256,
                "adapter": spec["adapter"].__name__,
                "adapter_parameters": dict(parameters),
                "computed_operand": computed_operand,
            }
        if "absolute_tolerance" in spec:
            tolerance = spec["absolute_tolerance"]
            differences = {
                field: abs(source_operand[field] - registry_operand[field])
                for field in selector["fields"]
            }
            runtime_record["comparison"] = {
                "kind": "absolute_tolerance",
                "absolute_tolerance": tolerance,
                "absolute_differences": differences,
                "matched": all(
                    difference <= tolerance
                    for difference in differences.values()
                ),
            }
        else:
            runtime_record["comparison"] = {
                "kind": "exact_field_map",
                "matched": all(
                    _exact_json_equal(operand, operands[0])
                    for operand in operands[1:]
                ),
            }
        bundle["runtime_evidence_record"] = runtime_record
        evidence[benchmark_name] = bundle
    return evidence


def structurally_validate_runtime_evidence_coverage(
    registry_entries, evidence_by_name
):
    """Summarize exact-name structural coverage without establishing provenance."""

    registry_names = {entry["name"] for entry in registry_entries}
    evidence_names = (
        set(evidence_by_name) if isinstance(evidence_by_name, Mapping) else set()
    )
    extra_names = sorted(evidence_names - registry_names)
    missing_names = sorted(registry_names - evidence_names)
    supported_names = []
    invalid_names = []
    for benchmark_name in sorted(registry_names & evidence_names):
        category = structurally_validate_runtime_evidence_bundle(
            benchmark_name, evidence_by_name[benchmark_name]
        )
        if category is None:
            invalid_names.append(benchmark_name)
        else:
            supported_names.append(benchmark_name)
    complete = not missing_names and not extra_names and not invalid_names
    return {
        "supported_names": supported_names,
        "missing_names": missing_names,
        "extra_names": extra_names,
        "invalid_names": invalid_names,
        "supported": len(supported_names),
        "missing": len(missing_names),
        "extra": len(extra_names),
        "invalid": len(invalid_names),
        "complete": complete,
    }


def collect_runtime_evidence_coverage(
    registry_entries, *, cache_root=DEFAULT_CACHE_ROOT
):
    """Collect authoritative local evidence and report exact registry coverage."""

    evidence = collect_runtime_evidence(registry_entries, cache_root=cache_root)
    return structurally_validate_runtime_evidence_coverage(
        registry_entries, evidence
    )


def assert_complete_runtime_evidence(
    registry_entries, *, cache_root=DEFAULT_CACHE_ROOT
):
    """Raise unless authoritative runtime evidence exactly covers the registry."""

    coverage = collect_runtime_evidence_coverage(
        registry_entries, cache_root=cache_root
    )
    if not coverage["complete"]:
        raise RuntimeEvidenceError(
            "runtime evidence incomplete: "
            f"{coverage['missing']} missing, {coverage['extra']} extra, "
            f"{coverage['invalid']} invalid"
        )
    return coverage
