"""Transcribe the BASS-II test catalog (Appendix A, Tables A.1-A.6) of NASA/TM-20210011385.

Two steps, both deterministic:

1. ``--pdf-dir DIR`` (one-off, needs ``pip install pdfplumber``): read the report PDFs and
   write two source snapshots that are committed to the repo, so every later step and every
   test runs without the PDF:
     data/raw/source/appendix_a_cells.json   one record per table row: the raw text of every
                                             column cell, located by the table's ruling lines
     data/raw/source/tm20210011385_pages.json  whitespace-normalized text of every page, keyed by
                                             the PRINTED page number (PDF page - 8)
2. (default) build ``data/raw/bass2_appendix_a_tests.csv`` from the cell snapshot.

How the tables are read. The Appendix A tables are landscape pages with full ruling lines.
pdfplumber finds the cell grid from those lines; each column is identified by its header
text (the headers are rotated, so their characters come out reversed and are matched both
ways). A table row that has a Test number starts a new test; following grid rows without a
Test number are wrapped continuation lines of the same test. The text of each column is read
once from the union of that test's cells, using character centres, so nothing is duplicated.

Nothing is inferred here except the documented mapping of the verbatim material text to a
material family and of numbers that are written in the row itself (thickness, width,
diameter). Every judgment call is listed in docs/data/extraction_audit.md.

Run from the repo root:
    python -m src.data_pipeline.extract_appendix_a                 # rebuild the CSV from the snapshot
    python -m src.data_pipeline.extract_appendix_a --pdf-dir PDFS  # re-extract the snapshots first
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "data" / "raw" / "source"
CELLS_JSON = SOURCE_DIR / "appendix_a_cells.json"
PAGES_JSON = SOURCE_DIR / "tm20210011385_pages.json"
CATALOG_CSV = ROOT / "data" / "raw" / "bass2_appendix_a_tests.csv"

REPORT = "NASA/TM-20210011385 (BASS-II Summary Report, 2021)"
PDF_TO_PRINTED_OFFSET = 8  # PDF page 11 carries printed page 3, PDF page 111 printed page 103, ...

# PDF page -> (printed page, table). Table A.1 starts on PDF page 111 (printed 103).
APPENDIX_PAGES = {111: (103, "A.1"), 112: (104, "A.1"), 113: (105, "A.2"), 114: (106, "A.3"), 115: (107, "A.3"),
                  116: (108, "A.4"), 117: (109, "A.4"), 118: (110, "A.5"), 119: (111, "A.5"), 120: (112, "A.6"),
                  121: (113, "A.6")}
PI_BY_TABLE = {"A.1": "Bhattacharjee", "A.2": "Ferkul", "A.3": "Fernandez-Pello", "A.4": "Miller", "A.5": "Olson",
               "A.6": "T'ien"}

# Header text (as printed) -> internal column key. Order matters: specific before generic.
HEADER_KEYS = [
    ("As-run test number", "as_run"), ("Test number", "test_id"), ("Sample number", "sample_number"),
    ("Material", "material"), ("Igniter", "igniter"), ("Flow restrictor", "flow_restrictor"),
    ("Sample distance", "sample_distance"), ("Fan display", "fan_display"), ("Air display", "air_display"),
    ("Calibrated initial O2", "cal_o2_initial"), ("Calibrated final O2", "cal_o2_final"),
    ("Initial O2", "o2_initial"), ("Final O2", "o2_final"), ("Leap", "date"), ("Approximate start", "time"),
    ("Test observations", "observations"),
]

CATALOG_COLUMNS = [
    "pi_table", "pi", "as_run_number", "test_id", "gmt_date_raw", "sample_number",
    "material_raw", "material_family", "pmma_color", "thickness_mm", "width_cm", "diameter_mm",
    "flow_configuration", "fan_display_raw", "air_display_raw",
    "cal_o2_initial", "cal_o2_final", "o2_initial_raw", "o2_final_raw",
    "observations_raw", "source_page",
    # extra provenance / quality columns
    "pdf_page", "flow_configuration_raw", "flow_configuration_source", "cal_o2_initial_raw", "cal_o2_final_raw",
    "o2_flag", "flow_restrictor_raw", "igniter_raw", "sample_reuse_of", "catalog_notes",
]

O2_PLAUSIBLE = (10.0, 30.0)


# --------------------------------------------------------------------------- #
# Text normalization (shared with the derivation step and the tests)
# --------------------------------------------------------------------------- #
def join_cell_lines(text: str) -> str:
    """Join the wrapped lines of one table cell into one line.

    A line that ends with an ASCII hyphen is joined without a space ("0.2-" + "mm" -> "0.2-mm",
    "self-" + "extinguished" -> "self-extinguished"); every other line break becomes one space.
    """
    lines = [ln.strip() for ln in str(text or "").split("\n") if ln.strip()]
    out = ""
    for ln in lines:
        if not out:
            out = ln
        elif out.endswith("-") and not out.endswith(" -") and not out.endswith("--"):
            out += ln
        else:
            out += " " + ln
    return re.sub(r"[ \t]+", " ", out).strip()


def normalize_ws(text: str) -> str:
    """Collapse all whitespace to single spaces (used for page text and quote checks)."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


# --------------------------------------------------------------------------- #
# Step 1: PDF -> snapshots (needs pdfplumber; not needed at runtime)
# --------------------------------------------------------------------------- #
def _header_name(h: str | None) -> str | None:
    if not h:
        return None
    flat = h.replace("\n", " ")
    for cand in (flat, flat[::-1]):
        for key, name in HEADER_KEYS:
            if re.search(r"\b" + re.escape(key), cand, flags=re.I):
                if name in ("o2_initial", "o2_final") and "alibrated" in cand:
                    continue
                if name == "test_id" and "As-run" in cand:
                    continue
                return name
    return None


def _text_in(page: Any, x0: float, top: float, x1: float, bottom: float) -> str:
    def inside(o: dict) -> bool:
        if o.get("object_type") != "char":
            return True
        cx, cy = (o["x0"] + o["x1"]) / 2, (o["top"] + o["bottom"]) / 2
        return x0 <= cx <= x1 and top <= cy <= bottom
    return (page.filter(inside).crop((x0, top, x1, bottom)).extract_text() or "").strip()


def extract_cells(pdf_path: Path) -> list[dict[str, Any]]:
    """One record per Appendix A test with the raw text of each identified column."""
    import pdfplumber  # local import: only needed for re-extraction

    records: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        first_pdf_page = _first_pdf_page(pdf_path)
        for pdf_page, (printed, table) in APPENDIX_PAGES.items():
            page = pdf.pages[pdf_page - first_pdf_page]
            tables = page.find_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            if len(tables) != 1:
                raise RuntimeError(f"PDF page {pdf_page}: expected one table, found {len(tables)}")
            t = tables[0]
            cols = []
            for cell, txt in zip(t.rows[0].cells, t.extract()[0]):
                name = _header_name(txt) if cell is not None else None
                if name:
                    cols.append((cell[0], cell[2], name))
            names = [c[2] for c in cols]
            if len(set(names)) != len(names) or "test_id" not in names or "observations" not in names:
                raise RuntimeError(f"PDF page {pdf_page}: unexpected header {names}")

            def col_of(c):
                xc = (c[0] + c[2]) / 2
                return next((n for a, b, n in cols if a - 0.5 <= xc <= b + 0.5), None)

            groups: list[dict[str, Any]] = []
            for r in t.rows[1:]:
                cells: dict[str, list] = {}
                for c in r.cells:
                    if c is not None and (n := col_of(c)):
                        cells.setdefault(n, []).append(c)
                if "".join(_text_in(page, *c) for c in cells.get("test_id", [])):
                    groups.append({"top": r.bbox[1], "bottom": r.bbox[3], "cells": cells, "grid_rows": 1})
                else:
                    g = groups[-1]
                    g["bottom"], g["grid_rows"] = r.bbox[3], g["grid_rows"] + 1
                    for k, v in cells.items():
                        g["cells"].setdefault(k, []).extend(v)
            for g in groups:
                rec: dict[str, Any] = {"pi_table": table, "pdf_page": pdf_page, "source_page": printed,
                                       "grid_rows": g["grid_rows"]}
                for _, _, n in cols:
                    cs = g["cells"].get(n)
                    rec[n] = _text_in(page, min(c[0] for c in cs), g["top"], max(c[2] for c in cs), g["bottom"]) if cs else ""
                records.append(rec)
    return records


def _first_pdf_page(pdf_path: Path) -> int:
    """The split PDFs are named like '...-TM-20210011385-95-125.pdf' (first and last PDF page)."""
    m = re.search(r"TM-20210011385-(\d+)-(\d+)", pdf_path.name)
    if not m:
        raise ValueError(f"cannot read the PDF page range from {pdf_path.name}")
    return int(m.group(1))


def extract_pages(pdf_paths: list[Path]) -> dict[str, str]:
    """Whitespace-normalized page text keyed by printed page number (as a string)."""
    import pdfplumber

    pages: dict[str, str] = {}
    for path in pdf_paths:
        start = _first_pdf_page(path)
        if "-46-94-26-" in path.name:  # second half of the 46-94 split starts at PDF page 71
            start = 71
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                printed = start + i - PDF_TO_PRINTED_OFFSET
                if printed < 1:
                    continue
                pages[str(printed)] = normalize_ws(page.extract_text(y_tolerance=5) or "")  # y_tolerance 5 keeps subscripts (O2) on their line
    return dict(sorted(pages.items(), key=lambda kv: int(kv[0])))


# --------------------------------------------------------------------------- #
# Step 2: snapshot -> catalog CSV
# --------------------------------------------------------------------------- #
def _num(s: str) -> float | None:
    s = str(s or "").strip()
    return float(s) if re.fullmatch(r"\d+(\.\d+)?", s) else None


def material_family(material: str, pi_table: str) -> str:
    """Map the verbatim material text to a family (rules documented in extraction_audit.md)."""
    m = material.lower()
    if "nomex" in m:
        return "Nomex"
    if "candle" in m or "wax" in m:
        return "candle_wax"
    if "spherical" in m:
        return "PMMA_sphere"
    if "sibal" in m or (pi_table == "A.6" and re.match(r"\d cm si\b", m)):
        return "SIBAL_fabric"
    if "rod" in m:
        return "PMMA_rod"
    if "film" in m:
        return "PMMA_film"
    if "slab" in m:
        return "PMMA_slab"
    if "pmma" in m or pi_table == "A.1":
        th = thickness_mm(material)
        if th is None:
            return "other"
        return "PMMA_film" if th < 1.0 else "PMMA_slab"
    return "other"


def pmma_color(material: str) -> str:
    m = material.lower()
    return "black" if "black" in m else ("clear" if "clear" in m else "")


def thickness_mm(material: str) -> float | None:
    """Sheet thickness written in the material text (µm converted to mm). Rods and fabric: None."""
    m = material.replace("μ", "µ")
    if re.search(r"rod|sibal|spherical|candle|nomex", m, flags=re.I):
        return None
    hit = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*µm", m)
    if hit:
        return round(float(hit.group(1)) / 1000.0, 4)
    hit = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*mm(?:-|\s)*thick", m) or re.search(r"(\d+(?:\.\d+)?)\s*-?\s*mm\b", m)
    if hit:
        return float(hit.group(1))
    return None


def width_cm(material: str) -> float | None:
    """Sample width written in the material text. A '... cm thick' value is NOT read as a width."""
    m = material
    if re.search(r"rod|spherical|candle", m, flags=re.I):
        return None
    hit = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*cm(?:-|\s)*wide", m)
    if hit:
        return float(hit.group(1))
    if re.search(r"\d\s*cm\s+thick", m):
        return None  # e.g. M5 "3-mm-thick PMMA, two-sided, 2 cm thick": width not stated as such
    hit = re.search(r"(?:^|[\s,])(\d+(?:\.\d+)?)\s*-?\s*cm\b", m)
    return float(hit.group(1)) if hit else None


def diameter_mm(material: str) -> float | None:
    if not re.search(r"rod", material, flags=re.I):
        return None
    hit = re.search(r"(\d+(?:\.\d+)?)-mm", material)
    return float(hit.group(1)) if hit else None


def flow_configuration(raw: str, family: str) -> tuple[str, str]:
    """(configuration, source). The 'Sample distance' column holds Opposed/Concurrent/Stagnation."""
    r = raw.strip().lower()
    if r in ("opposed", "concurrent", "stagnation"):
        return r, "Appendix A row ('Sample distance' column)"
    if r == "?":
        return "unknown", "Appendix A row shows '?'"
    if family == "SIBAL_fabric":
        # Table 7.1 title: "TEST SUMMARY OF FLAT SIBAL FABRICS IN CONCURRENT FLOW" (printed p. 96)
        return "concurrent", "Table 7.1 title 'FLAT SIBAL FABRICS IN CONCURRENT FLOW' (p. 96); row shows " + repr(raw.strip())
    return "unknown", f"row shows {raw.strip()!r}"


def o2_flag(cal_i: float | None, cal_f: float | None) -> str:
    lo, hi = O2_PLAUSIBLE
    flags = []
    for name, v in (("cal_o2_initial", cal_i), ("cal_o2_final", cal_f)):
        if v is not None and not (lo <= v <= hi):
            flags.append(f"{name}={v:g} outside {lo:g}-{hi:g} vol%")
    return "; ".join(flags)


AS_RUN_ORDER_NOTE = "later use (higher as-run test number) of sample {s}, first used in {first}"


def build_catalog(cells: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for c in cells:
        mat = join_cell_lines(c.get("material", ""))
        fam = material_family(mat, c["pi_table"])
        cfg, cfg_src = flow_configuration(join_cell_lines(c.get("sample_distance", "")), fam)
        ci_raw, cf_raw = join_cell_lines(c.get("cal_o2_initial", "")), join_cell_lines(c.get("cal_o2_final", ""))
        ci, cf = _num(ci_raw), _num(cf_raw)
        rows.append({
            "pi_table": c["pi_table"], "pi": PI_BY_TABLE[c["pi_table"]],
            "as_run_number": int(join_cell_lines(c["as_run"])), "test_id": join_cell_lines(c["test_id"]),
            "gmt_date_raw": join_cell_lines(c.get("date", "")), "sample_number": join_cell_lines(c.get("sample_number", "")),
            "material_raw": mat, "material_family": fam,
            "pmma_color": pmma_color(mat) if fam.startswith("PMMA") else "",
            "thickness_mm": thickness_mm(mat), "width_cm": width_cm(mat), "diameter_mm": diameter_mm(mat),
            "flow_configuration": cfg,
            "fan_display_raw": join_cell_lines(c.get("fan_display", "")),
            "air_display_raw": join_cell_lines(c.get("air_display", "")),
            "cal_o2_initial": ci, "cal_o2_final": cf,
            "o2_initial_raw": join_cell_lines(c.get("o2_initial", "")), "o2_final_raw": join_cell_lines(c.get("o2_final", "")),
            "observations_raw": join_cell_lines(c.get("observations", "")),
            "source_page": int(c["source_page"]), "pdf_page": int(c["pdf_page"]),
            "flow_configuration_raw": join_cell_lines(c.get("sample_distance", "")), "flow_configuration_source": cfg_src,
            "cal_o2_initial_raw": ci_raw, "cal_o2_final_raw": cf_raw, "o2_flag": o2_flag(ci, cf),
            "flow_restrictor_raw": join_cell_lines(c.get("flow_restrictor", "")),
            "igniter_raw": join_cell_lines(c.get("igniter", "")),
        })
    df = pd.DataFrame(rows)
    # Sample reuse: the same sample number used again in a later test (as-run numbers are global, 1-126).
    key = df["sample_number"].str.strip().str.lower()
    df["sample_reuse_of"] = ""
    for s, grp in df.groupby(key):
        if len(grp) > 1 and s:
            g = grp.sort_values("as_run_number")
            first = g.iloc[0]["test_id"]
            for idx in g.index[1:]:
                df.at[idx, "sample_reuse_of"] = first
    df["catalog_notes"] = df.apply(_notes, axis=1)
    df = df.sort_values(["pi_table", "as_run_number"]).reset_index(drop=True)
    return df[CATALOG_COLUMNS]


def _notes(r: pd.Series) -> str:
    notes = []
    if r["sample_reuse_of"]:
        notes.append(f"same sample number as {r['sample_reuse_of']} (earlier as-run test)")
    if "2018" in r["gmt_date_raw"]:
        notes.append("date printed as 2018; BASS-II ran in 2014 (kept verbatim)")
    if r["material_family"] == "PMMA_slab" and r["width_cm"] is None:
        notes.append("width not stated as a width in the material text")
    return "; ".join(notes)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pdf-dir", type=Path, default=None, help="directory with the split report PDFs (re-extract)")
    args = ap.parse_args()
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    if args.pdf_dir:
        pdfs = sorted(args.pdf_dir.glob("*TM-20210011385-*.pdf"))
        appendix = next(p for p in pdfs if "-95-125" in p.name)
        cells = extract_cells(appendix)
        CELLS_JSON.write_text(json.dumps(cells, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        PAGES_JSON.write_text(json.dumps(extract_pages(pdfs), indent=0, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {CELLS_JSON.relative_to(ROOT)} ({len(cells)} records) and {PAGES_JSON.relative_to(ROOT)}")
    cells = json.loads(CELLS_JSON.read_text(encoding="utf-8"))
    cat = build_catalog(cells)
    cat.to_csv(CATALOG_CSV, index=False)
    print(f"Catalog: {len(cat)} tests -> {CATALOG_CSV.relative_to(ROOT)}")
    print(cat.groupby("pi_table").size().to_string())


if __name__ == "__main__":
    main()
