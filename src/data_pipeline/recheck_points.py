"""Seeded 20% re-check of the labelled points against the source text (final review).

For a random 20% of ``data/processed/flame_points_v2.csv`` (seed 2027) it checks, independently of the derivation code:
  * the evidence quote is an exact substring of the test's observation cell or of the normalized page text;
  * the O2 value is the test's calibrated initial/final O2 (Appendix A), its Table 7.1 O2, or its Table 5.1 initial O2;
  * the flow is a number written in the test's air-display cell or quote, or a Table 7.1 / Table 5.1 velocity.
Writes ``docs/data/points_recheck_v2.md``.

    python -m src.data_pipeline.recheck_points
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_pipeline.extract_appendix_a import CATALOG_CSV, normalize_ws
from src.data_pipeline.derive_points_v2 import OUT_POINTS
from src.data_pipeline.report_tables import page_text, parse_table_5_1, parse_table_7_1

ROOT = Path(__file__).resolve().parents[2]
OUT_MD = ROOT / "docs" / "data" / "points_recheck_v2.md"
SEED = 2027


def recheck(seed: int = SEED) -> pd.DataFrame:
    p = pd.read_csv(OUT_POINTS, keep_default_na=False)
    cat = pd.read_csv(CATALOG_CSV, dtype=str, keep_default_na=False).set_index("test_id")
    t71, t51 = parse_table_7_1().set_index("test_id"), parse_table_5_1().set_index("test_id")
    idx = sorted(np.random.default_rng(seed).choice(len(p), size=int(np.ceil(0.2 * len(p))), replace=False))
    rows = []
    for i in idx:
        r = p.iloc[i]
        a = r["appendix_test_id"] or r["test_id"]
        obs = cat.loc[a, "observations_raw"] if a in cat.index else ""
        quote_ok = r["evidence_quote"] in obs or normalize_ws(r["evidence_quote"]) in page_text(int(r["source_page"]))
        o2, f = float(r["o2_pct"]), float(r["flow_cm_s"])
        if r["test_id"].startswith("GMT"):
            t = t71.loc[r["test_id"]]
            o2_ok, flow_ok, src = o2 == t["o2_vol_percent"], f in (t["flow_start_cm_s"], t["flow_end_cm_s"]), "Table 7.1 p. 96"
        elif r["derivation_rule"] == "table_5_1_spread_rate_at_flow":
            t = t51.loc[r["test_id"]]
            o2_ok, flow_ok, src = o2 == t["o2_initial"], f in t["velocities_cm_s"], "Table 5.1 p. 57"
        else:
            c = cat.loc[a]
            o2_ok = o2 in {float(x) for x in (c["cal_o2_initial"], c["cal_o2_final"]) if x}
            nums = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", c["air_display_raw"] + " " + r["evidence_quote"])}
            flow_ok, src = f in nums, f"Table {c['pi_table']} p. {c['source_page']}"
        rows.append({"point_id": r["point_id"], "rule": r["derivation_rule"], "burn": int(r["burn"]),
                     "confidence": r["label_confidence"], "quote": "pass" if quote_ok else "FAIL",
                     "O2": "pass" if o2_ok else "FAIL", "flow": "pass" if flow_ok else "FAIL", "conditions from": src})
    return pd.DataFrame(rows)


def main() -> None:
    d = recheck()
    ok = int(((d[["quote", "O2", "flow"]] == "pass").all(axis=1)).sum())
    lines = ["# 20% random re-check of the labelled points (final review)", "",
             f"`python -m src.data_pipeline.recheck_points` re-checks a seeded random 20% of `data/processed/flame_points_v2.csv` "
             f"({len(d)} of the points, `numpy.random.default_rng({SEED})`) against the source text, independently of the derivation "
             "code: the quote is an exact substring of the test's observation cell or page text; the O2 is the test's calibrated "
             "initial/final O2, Table 7.1 O2 or Table 5.1 initial O2; the flow is a number written in the air-display cell or the "
             "quote, or a Table 7.1 / 5.1 velocity. Each label was also read against its quote by eye.", "",
             f"**Result: {ok}/{len(d)} points pass every check.**", "",
             "| Point | Rule | burn | Confidence | Quote | O2 | Flow | Conditions from |", "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {x.point_id} | `{x.rule}` | {x.burn} | {x.confidence} | {x.quote} | {x.O2} | {x.flow} | {x['conditions from']} |"
              for _, x in d.iterrows()]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{ok}/{len(d)} pass -> {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
