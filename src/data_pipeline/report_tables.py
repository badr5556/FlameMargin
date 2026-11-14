"""Parse the two text tables of NASA/TM-20210011385 that summarize test conditions per PI.

* Table 7.1 (printed p. 96): SIBAL fabric tests (T'ien), the PI's curated width / flow / O2 summary.
* Table 5.1 (printed p. 57): twenty Miller PMMA-slab tests with thickness, width, sides, velocity,
  measured spread rate, burn time and initial/final O2.

Both are parsed from the committed page-text snapshot (data/raw/source/tm20210011385_pages.json),
never from figures. ``row_text`` keeps the exact (whitespace-normalized) substring of the page that a
row was parsed from, so every value can be traced back with a plain text search.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PAGES_JSON = ROOT / "data" / "raw" / "source" / "tm20210011385_pages.json"

_NUM = r"\d+(?:\.\d+)?"


@lru_cache(maxsize=1)
def pages() -> dict[str, str]:
    return json.loads(PAGES_JSON.read_text(encoding="utf-8"))


def page_text(printed_page: int | str) -> str:
    return pages()[str(printed_page)]


# --------------------------------------------------------------------------- #
# Table 7.1
# --------------------------------------------------------------------------- #
T71_PAGE = 96
_T71_ROW = re.compile(
    rf"(GMT\d+-T\d+[ab]?) ({_NUM}) ({_NUM}(?: to {_NUM})?) ({_NUM})(b?) "
    rf"(-{{5,}}|Quenched|No blowoff|No ignition|Blow-off|Reused, [a-z -]+?|BASS)(?= GMT| a[A-Z]|$)"
)


def parse_table_7_1(text: str | None = None) -> pd.DataFrame:
    text = page_text(T71_PAGE) if text is None else text
    rows = []
    for m in _T71_ROW.finditer(text):
        tid, width, flow, o2, foot, comment = m.groups()
        f = [float(x) for x in flow.split(" to ")]
        rows.append({
            "test_id": tid, "sample_width_cm": float(width), "flow_start_cm_s": f[0], "flow_end_cm_s": f[-1],
            "o2_vol_percent": float(o2), "o2_footnote_b": foot == "b",
            "comment": "" if comment.startswith("-") else comment, "row_text": m.group(0), "source_page": T71_PAGE,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Table 5.1
# --------------------------------------------------------------------------- #
T51_PAGE = 57
_LIST = rf"{_NUM}(?:(?:, | and |, and ){_NUM})*"
_T51_ROW = re.compile(
    rf"\b(M\d+) ({_NUM}) ({_NUM}) ([12]) ({_LIST}) ({_LIST}|Not tracked) ({_NUM}) ({_NUM}) ({_NUM})(?= M\d+ | Figure|$)"
)


def _split_list(s: str) -> list[float]:
    return [float(x) for x in re.findall(_NUM, s)]


def parse_table_5_1(text: str | None = None) -> pd.DataFrame:
    text = page_text(T51_PAGE) if text is None else text
    rows = []
    for m in _T51_ROW.finditer(text):
        tid, th, w, sides, vel, rate, burn, o2i, o2f = m.groups()
        v = _split_list(vel)
        r = _split_list(rate) if rate != "Not tracked" else []
        if r and len(r) != len(v):
            raise ValueError(f"Table 5.1 {tid}: {len(v)} velocities but {len(r)} spread rates")
        rows.append({
            "test_id": tid, "thickness_mm": float(th), "width_cm": float(w), "sides_burning": int(sides),
            "velocities_cm_s": v, "spread_rates_mm_s": r, "spread_rate_tracked": rate != "Not tracked",
            "burn_time_min": float(burn), "o2_initial": float(o2i), "o2_final": float(o2f),
            "row_text": m.group(0), "source_page": T51_PAGE,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    t71, t51 = parse_table_7_1(), parse_table_5_1()
    print(f"Table 7.1: {len(t71)} rows; Table 5.1: {len(t51)} rows")
    print(t71.drop(columns="row_text").to_string())
    print(t51.drop(columns="row_text").to_string())
