"""Safety operating point and reliability plot for the shipped model, from its leave-one-test-out predictions.

    python -m src.safety_eval     # writes models/safety_operating_point.json and docs/img/reliability.png (needs kaleido)

For fire safety the costly error is a missed burn: calling a condition "won't burn" when NASA saw it burn. This reports, on the
out-of-fold (leave-one-test-out) P(burn) of the shipped model stored in models/flame_model_v2.joblib:
  * burn recall (sensitivity), the miss rate and the false-"safe" rate at the verdict threshold 0.5;
  * the same at the safety threshold: the LARGEST threshold whose burn recall is >= 0.95;
  * the extinguished recall (specificity) at both.
The verdict logic in src/api.py is not changed (burn if P(burn) >= 0.5); the app only shows the safety threshold next to it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src import model_v2

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "models" / "safety_operating_point.json"
OUT_PNG = ROOT / "docs" / "img" / "reliability.png"
TARGET_BURN_RECALL = 0.95
VERDICT_THRESHOLD = 0.5
BINS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
MODEL_NAMES = {"logreg21": "engine v2.1", "logreg": "engine v2"}


def oof_predictions() -> tuple[np.ndarray, np.ndarray, str]:
    """(y, out-of-fold P(burn), model name) of the shipped model, as stored by python -m src.model_v2."""
    art = model_v2.load_artifact_v2(allow_retrain=False)
    name = art["chosen_model"]
    y = np.array([int(p["burn"]) for p in art["points"]])
    return y, np.asarray(art["loto_oof"][name], dtype=float), name


def at_threshold(y: np.ndarray, p: np.ndarray, t: float) -> dict[str, Any]:
    """Confusion counts with 'burn' = P(burn) >= t (same tie rule as the API: 2-decimal rounding)."""
    call_burn = np.round(p, 2) >= t
    burn, ext = y == 1, y == 0
    tp, fn = int((call_burn & burn).sum()), int((~call_burn & burn).sum())
    tn, fp = int((~call_burn & ext).sum()), int((call_burn & ext).sum())
    n_safe_calls = tn + fn
    return {
        "threshold": round(float(t), 2),
        "burn_recall": round(tp / max(tp + fn, 1), 3),
        "missed_burns": fn, "n_burn": int(burn.sum()),
        "miss_rate": round(fn / max(tp + fn, 1), 3),
        "false_safe_rate": round(fn / n_safe_calls, 3) if n_safe_calls else None,
        "n_safe_calls": n_safe_calls,
        "extinguished_recall": round(tn / max(tn + fp, 1), 3),
        "n_extinguished": int(ext.sum()),
    }


def safety_threshold(y: np.ndarray, p: np.ndarray, target: float = TARGET_BURN_RECALL) -> float:
    """Largest threshold (2-decimal grid) whose burn recall is >= target."""
    best = 0.0
    for t in np.round(np.arange(0.0, 1.0001, 0.01), 2):
        if at_threshold(y, p, float(t))["burn_recall"] >= target:
            best = float(t)
    return best


def reliability(y: np.ndarray, p: np.ndarray) -> list[dict[str, Any]]:
    return model_v2.reliability_table(y, p, BINS)


def compute() -> dict[str, Any]:
    y, p, name = oof_predictions()
    t_safe = safety_threshold(y, p)
    return {
        "model": name, "validation": "leave-one-test-out, out-of-fold P(burn) of the shipped model",
        "n_points": int(len(y)),
        "definitions": {
            "burn_recall": "share of NASA burn points called 'burn' (P(burn) >= threshold)",
            "miss_rate": "share of NASA burn points called 'won't burn' (1 - burn recall)",
            "false_safe_rate": "share of 'won't burn' calls that were NASA burn points",
            "extinguished_recall": "share of NASA extinguished points called 'won't burn'",
        },
        "verdict_threshold": at_threshold(y, p, VERDICT_THRESHOLD),
        "target_burn_recall": TARGET_BURN_RECALL,
        "safety_threshold": at_threshold(y, p, t_safe),
        "reliability": reliability(y, p),
        "readout_rule": "verdict BURN if P(burn) >= 0.5 (unchanged); the readout also flags 'may burn' when the safety "
                        "threshold <= P(burn) < 0.5",
    }


def reliability_figure(rows: list[dict[str, Any]], model: str):
    import plotly.graph_objects as go

    r = [x for x in rows if x["n"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration",
                             line=dict(color="#c3c2b7", dash="dot", width=2), hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=[x["mean_predicted"] for x in r], y=[x["observed_burn_rate"] for x in r], mode="lines+markers+text",
        name=f"{MODEL_NAMES.get(model, model).capitalize()}, leave-one-test-out", line=dict(color="#3987e5", width=2),
        marker=dict(size=[8 + 2.2 * np.sqrt(x["n"]) for x in r], color="#3987e5", line=dict(color="#0e1117", width=2)),
        text=[f"n={x['n']}" for x in r], textposition=["top right" if x["mean_predicted"] < 0.2 else "top left" for x in r], textfont=dict(color="#f0efec", size=12),
        customdata=[[x["bin"], x["n"]] for x in r],
        hovertemplate="bin %{customdata[0]} · n %{customdata[1]}<br>mean predicted %{x:.3f}<br>observed burn rate %{y:.3f}<extra></extra>",
    ))
    fig.update_layout(template="plotly_dark", height=430, margin=dict(l=10, r=10, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(title="Predicted P(burn), bin mean", range=[0, 1.02], dtick=0.2),
                      yaxis=dict(title="Observed burn rate", range=[-0.02, 1.08], dtick=0.2),
                      legend=dict(orientation="h", yanchor="top", y=-0.18, x=0))
    return fig


def main() -> None:
    res = compute()
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    try:
        fig = reliability_figure(res["reliability"], res["model"])
        fig.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", margin=dict(l=20, r=20, t=50, b=20),
                          title=dict(text="Reliability (calibration), leave-one-test-out, 192 NASA points", x=0.01))
        fig.write_image(str(OUT_PNG), width=900, height=560, scale=2)
        print(f"wrote {OUT_PNG.relative_to(ROOT)}")
    except Exception as e:  # noqa: BLE001 - kaleido is optional
        print(f"PNG skipped ({type(e).__name__}: install kaleido to export)")


if __name__ == "__main__":
    main()
