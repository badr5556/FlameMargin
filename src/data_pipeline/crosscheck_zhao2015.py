"""Cross-check the 31 SIBAL rows of Table 7.1 (NASA/TM-20210011385 p. 96) against the test table of
Zhao, T'ien, Ferkul, Olson (2015), "Concurrent Flame Growth, Spread and Extinction over Composite Fabric Samples in
Low Speed Purely Forced Flow in Microgravity", NTRS 20150008962.

Needs that paper's text (not committed): ``pdftotext -layout 20150008962.pdf zhao.txt``, then
    python src/data_pipeline/crosscheck_zhao2015.py zhao.txt
Compares width, start/end flow, O2 and the comment for every test id; prints the per-row result.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_pipeline.report_tables import parse_table_7_1  # noqa: E402

_N = r"\d+(?:\.\d+)?"
ROW = re.compile(rf"^\s*(GMT\d+-T\d+[ab]?)\s+({_N})\s+({_N})(?:\s*\S\s*({_N}))?\s+({_N})(\*?)\s*(.*?)\s*$")


def parse_zhao(text: str) -> dict[str, dict]:
    out = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            tid, w, f0, f1, o2, star, comment = m.groups()
            out[tid] = {"width": float(w), "f0": float(f0), "f1": float(f1 or f0), "o2": float(o2), "comment": comment}
    return out


def norm_comment(c: str) -> str:
    return re.sub(r"[\s-]+", " ", c.lower()).replace("blow off", "blowoff").strip()


def main(path: str) -> int:
    z = parse_zhao(Path(path).read_text(encoding="utf-8", errors="replace"))
    t = parse_table_7_1().set_index("test_id")
    ok = 0
    for tid, r in t.iterrows():
        zr = z.get(tid)
        same = zr is not None and (zr["width"], zr["f0"], zr["f1"], zr["o2"]) == (r["sample_width_cm"], r["flow_start_cm_s"],
                                                                            r["flow_end_cm_s"], r["o2_vol_percent"]) \
            and norm_comment(zr["comment"]) == norm_comment(r["comment"])
        ok += same
        print(f"{tid:12s} {'match' if same else 'DIFF'}  TM: {r['sample_width_cm']} {r['flow_start_cm_s']}->{r['flow_end_cm_s']} "
              f"{r['o2_vol_percent']} '{r['comment']}' | Zhao: {zr}")
    print(f"{ok}/{len(t)} rows match")
    return 0 if ok == len(t) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
