"""Derive binary burn/extinguish observation points from the BASS-II SIBAL extraction.

Each BASS-II test in Table 7.1 ramps the forced flow from ``flow_start_cm_s`` to
``flow_end_cm_s`` at a fixed O2 level, so one test can give up to two
observations. Only the written rules below are applied; nothing is
interpolated, padded or inferred beyond them. Every output row carries the
rule that produced it in ``derivation_rule``.

Rules (event -> observations)
  R1 quenched        burn=1 at (O2, flow_start): a flame existed before the ramp
                     burn=0 at (O2, flow_end):   the flame quenched
  R2 blowoff         burn=1 at (O2, flow_start); burn=0 at (O2, flow_end)
  R3 "No blowoff"    (comment, flow increased) burn=1 at (O2, flow_start) and
                     burn=1 at (O2, flow_end): the flame survived the increase
  R4 no_ignition     (non-reused) burn=0 at (O2, flow); ignition failure is a
                     conservative proxy for non-flammability

Excluded from training (kept for display as grey points): reused-sample rows
and rows with no definitive outcome.

Run from the repo root:
    python src/data_pipeline/derive_points.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]  # repo root
RAW = ROOT / "data" / "raw" / "bass2_sibal_table7_1_extracted.csv"
OUT_POINTS = ROOT / "data" / "processed" / "flame_points.csv"
OUT_DISPLAY = ROOT / "data" / "processed" / "display_only_points.csv"

POINT_COLUMNS = [
    "point_id", "test_id", "o2_pct", "flow_cm_s", "sample_width_cm", "burn",
    "derivation_rule", "source", "source_page",
]
DISPLAY_COLUMNS = [
    "test_id", "o2_pct", "flow_start_cm_s", "flow_end_cm_s", "sample_width_cm",
    "display_status", "reported_comment", "conservative_event_label", "source", "source_page", "notes",
]

RULES = {
    "R1_start": "R1 quenched: burn=1 at (O2, flow_start) because a flame existed before the flow ramp",
    "R1_end": "R1 quenched: burn=0 at (O2, flow_end) because the flame quenched",
    "R2_start": "R2 blowoff: burn=1 at (O2, flow_start) because a flame existed before the flow ramp",
    "R2_end": "R2 blowoff: burn=0 at (O2, flow_end) because the flame blew off",
    "R3_start": "R3 'No blowoff' with flow increased: burn=1 at (O2, flow_start) because a flame existed before the ramp",
    "R3_end": "R3 'No blowoff' with flow increased: burn=1 at (O2, flow_end) because the flame survived the increase",
    "R4": "R4 no_ignition (non-reused): burn=0 at (O2, flow); ignition failure is a conservative proxy for non-flammability",
}


def _is_reused(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes"}


def _point(row: pd.Series, which: str, flow: float, burn: int, rule_key: str) -> dict:
    return {
        "point_id": f"{row['test_id']}_{which}",
        "test_id": row["test_id"],
        "o2_pct": float(row["o2_vol_percent"]),
        "flow_cm_s": float(flow),
        "sample_width_cm": float(row["sample_width_cm"]),
        "burn": int(burn),
        "derivation_rule": RULES[rule_key],
        "source": row["source"],
        "source_page": row["source_page"],
    }


def derive(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (training points, display-only rows). Pure function, no I/O."""
    points: list[dict] = []
    display: list[dict] = []
    for _, row in raw.iterrows():
        label = str(row["conservative_event_label"]).strip()
        comment = "" if pd.isna(row["reported_comment"]) else str(row["reported_comment"]).strip()
        reused = _is_reused(row["reused_sample"])
        f0, f1 = float(row["flow_start_cm_s"]), float(row["flow_end_cm_s"])
        if reused:
            status = "reused_sample"
        elif label == "quenched":
            points += [_point(row, "start", f0, 1, "R1_start"), _point(row, "end", f1, 0, "R1_end")]
            continue
        elif label == "blowoff":
            points += [_point(row, "start", f0, 1, "R2_start"), _point(row, "end", f1, 0, "R2_end")]
            continue
        elif comment.lower() == "no blowoff" and f1 > f0:
            points += [_point(row, "start", f0, 1, "R3_start"), _point(row, "end", f1, 1, "R3_end")]
            continue
        elif label == "no_ignition":
            if f0 != f1:
                raise ValueError(f"{row['test_id']}: no_ignition with a flow ramp; rule R4 needs one flow")
            points.append(_point(row, "flow", f0, 0, "R4"))
            continue
        else:
            status = "outcome_not_reported"
        display.append({
            "test_id": row["test_id"], "o2_pct": float(row["o2_vol_percent"]),
            "flow_start_cm_s": f0, "flow_end_cm_s": f1, "sample_width_cm": float(row["sample_width_cm"]),
            "display_status": status, "reported_comment": comment,
            "conservative_event_label": label, "source": row["source"], "source_page": row["source_page"],
            "notes": "" if pd.isna(row["notes"]) else row["notes"],
        })
    return pd.DataFrame(points, columns=POINT_COLUMNS), pd.DataFrame(display, columns=DISPLAY_COLUMNS)


def sanity_summary(pts: pd.DataFrame) -> list[str]:
    """Literature sanity checks (printed and copied into docs/model_card.md)."""
    q_end = pts[pts["derivation_rule"] == RULES["R1_end"]]
    noign = pts[pts["derivation_rule"] == RULES["R4"]]
    lines = [
        f"Quench end-flows: {q_end['flow_cm_s'].min():g}-{q_end['flow_cm_s'].max():g} cm/s "
        f"(values: {', '.join(f'{v:g}' for v in sorted(q_end['flow_cm_s']))}); claim C3 reports quenching at 1-5 cm/s.",
        f"No-ignition O2: {noign['o2_pct'].min():g}-{noign['o2_pct'].max():g}% (low end of the tested 16.4-21.0% range).",
    ]
    return lines


def main() -> None:
    if not RAW.exists():
        raise FileNotFoundError(f"Raw input not found: {RAW}")
    raw = pd.read_csv(RAW, dtype={"test_id": "string"})
    pts, disp = derive(raw)
    OUT_POINTS.parent.mkdir(parents=True, exist_ok=True)
    pts.to_csv(OUT_POINTS, index=False)
    disp.to_csv(OUT_DISPLAY, index=False)
    n1, n0 = int((pts["burn"] == 1).sum()), int((pts["burn"] == 0).sum())
    print(f"Raw rows: {len(raw)}")
    print(f"Training points: {len(pts)} from {pts['test_id'].nunique()} tests -> {OUT_POINTS.relative_to(ROOT)}")
    print(f"Class balance: burn=1: {n1}, burn=0: {n0}")
    print(f"Display-only rows: {len(disp)} {disp['display_status'].value_counts().to_dict()} -> {OUT_DISPLAY.relative_to(ROOT)}")
    for line in sanity_summary(pts):
        print("Sanity: " + line)


if __name__ == "__main__":
    main()
