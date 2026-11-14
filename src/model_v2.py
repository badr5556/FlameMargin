"""FlameMargin Prediction Engine v2: multi-material training, validation and the saved artifact.

    python -m src.model_v2          # writes models/flame_model_v2.joblib, metrics_v2.json, metrics_history.json

Data: ``data/processed/flame_points_v2.csv`` (``include_in_training == True``), 5 material families from all
BASS-II tests of NASA/TM-20210011385 (Appendix A, Tables A.1-A.6; Table 7.1; Table 5.1).

Features
    o2_pct, log10_flow, log10_flow_sq, log10_thickness (0 when unknown) + thickness_missing,
    size_z (width_cm for flat samples, diameter_mm for rods, standardized within each family; 0 when unknown),
    fam_<family> one-hot, cfg_<configuration> one-hot.

Models (all scored with leave-one-test-out, grouped by test_id; settings fixed before training)
    baseline  DummyClassifier(strategy="prior")
    logreg    L2 logistic regression (C=1) + o2 x family interaction terms, standardized
    gpc       Gaussian process classifier, ConstantKernel*RBF + WhiteKernel, standardized
    hgb       HistGradientBoostingClassifier(max_depth=3, max_iter=100, learning_rate=0.1, min_samples_leaf=10,
              l2_regularization=1.0) with a monotonic increasing constraint on o2_pct

Selection: lowest LOTO Brier. Also reported: accuracy, balanced accuracy, log-loss, AUC, a reliability table,
per-family metrics, a leave-one-material-family-out stress test (reported only), monotonicity violations,
high-confidence-only sensitivity, a 90% bootstrap interval over tests (300 resamples) and per-family OOD rules.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
POINTS_V2 = ROOT / "data" / "processed" / "flame_points_v2.csv"
MODELS_DIR = ROOT / "models"
ARTIFACT_V2 = MODELS_DIR / "flame_model_v2.joblib"
METRICS_V2 = MODELS_DIR / "metrics_v2.json"
METRICS_V1 = MODELS_DIR / "metrics.json"
HISTORY = MODELS_DIR / "metrics_history.json"

ARTIFACT_VERSION = "2.0"
SEED = 42
N_BOOTSTRAP = 300
INTERVAL_LEVEL = 0.90
OOD_PERCENTILE = 95.0

FAMILIES = ["SIBAL_fabric", "PMMA_film", "PMMA_slab", "PMMA_rod", "Nomex"]
CONFIGS = ["opposed", "concurrent", "stagnation"]
FAMILY_LABELS = {
    "SIBAL_fabric": "SIBAL cotton-fiberglass fabric", "PMMA_film": "PMMA film (0.1–0.4 mm)",
    "PMMA_slab": "PMMA slab (1–5 mm)", "PMMA_rod": "PMMA rod (6.35–12.7 mm)", "Nomex": "Nomex III fabric",
}
SIZE_KIND = {"SIBAL_fabric": "width_cm", "PMMA_film": "width_cm", "PMMA_slab": "width_cm", "PMMA_rod": "diameter_mm", "Nomex": None}

BASE_FEATURES = (["o2_pct", "log10_flow", "log10_flow_sq", "log10_thickness", "thickness_missing", "size_z"]
                 + [f"fam_{f}" for f in FAMILIES] + [f"cfg_{c}" for c in CONFIGS])
INTERACTIONS = [f"o2_x_{f}" for f in FAMILIES]
DIST_FEATURES = ["o2_pct", "log10_flow", "size_z", "log10_thickness"]

MODEL_LABELS = {
    "baseline": "Prior baseline (training class rate)",
    "logreg": "Logistic regression (L2, o2 x material interaction)",
    "gpc": "Gaussian process classifier (RBF + White)",
    "hgb": "Gradient boosting (depth <= 3, monotone increasing in O2)",
}
MODEL_FEATURES = {"baseline": BASE_FEATURES, "logreg": BASE_FEATURES + INTERACTIONS, "gpc": BASE_FEATURES, "hgb": BASE_FEATURES}


# --------------------------------------------------------------------------- #
# Data + features
# --------------------------------------------------------------------------- #
def load_points_v2(path: Path = POINTS_V2, training_only: bool = True) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"test_id": "string", "point_id": "string"})
    if training_only:
        df = df[df["include_in_training"]].reset_index(drop=True)
    return df


def size_of(df: pd.DataFrame) -> np.ndarray:
    out = np.full(len(df), np.nan)
    for fam, kind in SIZE_KIND.items():
        if kind:
            m = (df["material_family"] == fam).to_numpy()
            out[m] = pd.to_numeric(df.loc[m, kind], errors="coerce").to_numpy()
    return out


def size_stats(df: pd.DataFrame) -> dict[str, list[float]]:
    s = size_of(df)
    stats = {}
    for fam in FAMILIES:
        v = s[(df["material_family"] == fam).to_numpy()]
        v = v[~np.isnan(v)]
        mu = float(v.mean()) if len(v) else 0.0
        sd = float(v.std()) if len(v) > 1 and v.std() > 0 else 1.0
        stats[fam] = [mu, sd]
    return stats


def feature_frame_v2(o2, flow, family, configuration, thickness_mm=None, size=None,
                     stats: dict[str, list[float]] | None = None) -> pd.DataFrame:
    """Model features for scalars or arrays (broadcast). ``size`` is width_cm (flat) or diameter_mm (rod)."""
    o2, flow, fam, cfg, th, sz = np.broadcast_arrays(
        np.asarray(o2, dtype=float), np.asarray(flow, dtype=float), np.asarray(family, dtype=object),
        np.asarray(configuration, dtype=object), np.asarray(np.nan if thickness_mm is None else thickness_mm, dtype=float),
        np.asarray(np.nan if size is None else size, dtype=float))
    o2, flow, fam, cfg, th, sz = (a.ravel() for a in (o2, flow, fam, cfg, th, sz))
    if np.any(flow <= 0):
        raise ValueError("flow must be > 0 cm/s (log scale)")
    lf = np.log10(flow)
    th_known = ~np.isnan(th) & (th > 0)
    out = {"o2_pct": o2, "log10_flow": lf, "log10_flow_sq": lf ** 2,
           "log10_thickness": np.where(th_known, np.log10(np.where(th_known, th, 1.0)), 0.0),
           "thickness_missing": (~th_known).astype(float)}
    z = np.zeros(len(o2))
    if stats is not None:
        for f in FAMILIES:
            m = (fam == f) & ~np.isnan(sz)
            mu, sd = stats[f]
            z[m] = (sz[m] - mu) / sd
    out["size_z"] = z
    for f in FAMILIES:
        out[f"fam_{f}"] = (fam == f).astype(float)
    for c in CONFIGS:
        out[f"cfg_{c}"] = (cfg == c).astype(float)
    for f in FAMILIES:
        out[f"o2_x_{f}"] = o2 * out[f"fam_{f}"]
    return pd.DataFrame(out)


def features_of_points(pts: pd.DataFrame, stats: dict[str, list[float]]) -> pd.DataFrame:
    return feature_frame_v2(pts["o2_pct"], pts["flow_cm_s"], pts["material_family"], pts["flow_configuration"],
                            pd.to_numeric(pts["thickness_mm"], errors="coerce"), size_of(pts), stats)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
def make_model(name: str):
    if name == "baseline":
        return DummyClassifier(strategy="prior")
    if name == "logreg":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
    if name == "gpc":
        kernel = ConstantKernel(1.0) * RBF(length_scale=1.0) + WhiteKernel(noise_level=1e-2)
        return make_pipeline(StandardScaler(), GaussianProcessClassifier(kernel=kernel, n_restarts_optimizer=1, random_state=0))
    if name == "hgb":
        cst = [1 if f == "o2_pct" else 0 for f in MODEL_FEATURES["hgb"]]
        return HistGradientBoostingClassifier(max_depth=3, max_iter=100, learning_rate=0.1, min_samples_leaf=10,
                                              l2_regularization=1.0, monotonic_cst=cst, random_state=0)
    raise KeyError(name)


class FittedModel:
    """A fitted estimator plus the feature list it uses and the per-family size stats it was trained with."""

    def __init__(self, name: str, est, stats: dict[str, list[float]]):
        self.name, self.est, self.stats = name, est, stats
        self.features = MODEL_FEATURES[name]

    def proba(self, F: pd.DataFrame) -> np.ndarray:
        return self.est.predict_proba(F[self.features])[:, 1]


def fit(name: str, pts: pd.DataFrame) -> FittedModel:
    stats = size_stats(pts)
    F = features_of_points(pts, stats)
    y = pts["burn"].to_numpy(dtype=int)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        est = make_model(name).fit(F[MODEL_FEATURES[name]], y)
    return FittedModel(name, est, stats)


def predict_points(model: FittedModel, pts: pd.DataFrame) -> np.ndarray:
    return model.proba(features_of_points(pts, model.stats))


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def score(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    y = np.asarray(y, dtype=int)
    p = np.clip(np.asarray(p, dtype=float), 0, 1)
    yhat = (p >= 0.5).astype(int)
    out = {
        "accuracy": round(float(accuracy_score(y, yhat)), 3),
        "balanced_accuracy": round(float(balanced_accuracy_score(y, yhat)), 3) if len(np.unique(y)) > 1 else None,
        "brier": round(float(brier_score_loss(y, p, pos_label=1)), 3),
        "log_loss": round(float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1])), 3),
        "auc": round(float(roc_auc_score(y, p)), 3) if len(np.unique(y)) > 1 else None,
        "n_points": int(len(y)), "n_burn": int(y.sum()),
    }
    return out


def reliability_table(y: np.ndarray, p: np.ndarray, edges=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)) -> list[dict[str, Any]]:
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1.0 else (p <= hi))
        rows.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(m.sum()),
                     "mean_predicted": round(float(p[m].mean()), 3) if m.any() else None,
                     "observed_burn_rate": round(float(y[m].mean()), 3) if m.any() else None})
    return rows


def loto_oof(name: str, pts: pd.DataFrame) -> np.ndarray:
    groups = pts["test_id"].to_numpy(dtype=str)
    p = np.zeros(len(pts))
    for tr, te in LeaveOneGroupOut().split(pts, groups=groups):
        train = pts.iloc[tr]
        if train["burn"].nunique() < 2:
            p[te] = train["burn"].mean()
            continue
        p[te] = predict_points(fit(name, train), pts.iloc[te])
    return p


def lomo_stress(name: str, pts: pd.DataFrame) -> dict[str, Any]:
    """Leave-one-material-family-out: train on the other families, score the held-out family (report only)."""
    out = {}
    for fam in FAMILIES:
        te = pts["material_family"] == fam
        if not te.any():
            continue
        m = fit(name, pts[~te].reset_index(drop=True))
        p = predict_points(m, pts[te].reset_index(drop=True))
        out[fam] = score(pts.loc[te, "burn"].to_numpy(), p)
    return out


def monotonicity(model: FittedModel, pts: pd.DataFrame, tol: float = 1e-3) -> dict[str, Any]:
    """Count O2 curves (per family, configuration and flow) where P(burn) drops as O2 rises."""
    curves, violated, max_drop, worst = 0, 0, 0.0, None
    for fam in FAMILIES:
        f = pts[pts["material_family"] == fam]
        if f.empty:
            continue
        o2 = np.round(np.arange(f["o2_pct"].min(), f["o2_pct"].max() + 1e-9, 0.1), 2)
        th = pd.to_numeric(f["thickness_mm"], errors="coerce").median()
        sz = np.nanmedian(size_of(f)) if SIZE_KIND[fam] else np.nan
        for cfg in sorted(f["flow_configuration"].unique()):
            for flow in np.unique(np.quantile(f["flow_cm_s"], [0.1, 0.5, 0.9]).round(2)):
                p = model.proba(feature_frame_v2(o2, flow, fam, cfg, th, sz, model.stats))
                d = np.diff(p)
                curves += 1
                if np.any(d < -tol):
                    violated += 1
                    if -d.min() > max_drop:
                        max_drop, worst = float(-d.min()), f"{fam}/{cfg} at {flow:g} cm/s"
    return {"curves": curves, "violated": violated, "max_drop": round(max_drop, 3), "worst_curve": worst}


def bootstrap_models(name: str, pts: pd.DataFrame, n: int = N_BOOTSTRAP, seed: int = SEED) -> tuple[list[FittedModel], int]:
    rng = np.random.default_rng(seed)
    tests = pts["test_id"].unique()
    idx_by = {t: np.flatnonzero(pts["test_id"].to_numpy() == t) for t in tests}
    out, redrawn = [], 0
    while len(out) < n:
        pick = rng.choice(tests, size=len(tests), replace=True)
        idx = np.concatenate([idx_by[t] for t in pick])
        sample = pts.iloc[idx].reset_index(drop=True)
        if sample["burn"].nunique() < 2:
            redrawn += 1
            continue
        out.append(fit(name, sample))
    return out, redrawn


def bootstrap_interval(boots: list[FittedModel], F: pd.DataFrame, level: float = INTERVAL_LEVEL) -> tuple[np.ndarray, np.ndarray]:
    B = np.vstack([b.proba(F) for b in boots])
    a = (1 - level) / 2
    return np.quantile(B, a, axis=0), np.quantile(B, 1 - a, axis=0)


# --------------------------------------------------------------------------- #
# Out-of-distribution: per-family envelope + kNN
# --------------------------------------------------------------------------- #
def family_envelopes(pts: pd.DataFrame) -> dict[str, dict[str, Any]]:
    env = {}
    for fam in FAMILIES:
        f = pts[pts["material_family"] == fam]
        th = pd.to_numeric(f["thickness_mm"], errors="coerce").dropna()
        sz = size_of(f)
        sz = sz[~np.isnan(sz)]
        env[fam] = {
            "o2_percent": [float(f["o2_pct"].min()), float(f["o2_pct"].max())],
            "flow_velocity_cm_s": [float(f["flow_cm_s"].min()), float(f["flow_cm_s"].max())],
            "thickness_mm": [float(th.min()), float(th.max())] if len(th) else None,
            "size": [float(sz.min()), float(sz.max())] if len(sz) else None,
            "size_kind": SIZE_KIND[fam],
            "configurations": sorted(f["flow_configuration"].unique().tolist()),
            "n_points": int(len(f)), "n_tests": int(f["test_id"].nunique()),
            "n_burn": int(f["burn"].sum()), "n_extinguished": int((f["burn"] == 0).sum()),
        }
    return env


def distance_space(pts: pd.DataFrame, stats: dict[str, list[float]]) -> dict[str, Any]:
    F = features_of_points(pts, stats)[DIST_FEATURES].to_numpy()
    mu, sd = F.mean(axis=0), F.std(axis=0)
    sd[sd == 0] = 1.0
    Z = (F - mu) / sd
    fam = pts["material_family"].to_numpy()
    groups = pts["test_id"].to_numpy(dtype=str)
    nn = []
    for i in range(len(Z)):
        m = (fam == fam[i]) & (groups != groups[i])
        nn.append(float(np.min(np.linalg.norm(Z[m] - Z[i], axis=1))) if m.any() else np.nan)
    nn = np.asarray(nn)
    return {"features": DIST_FEATURES, "mean": mu.tolist(), "std": sd.tolist(), "train_z": Z, "family": fam.tolist(),
            "loto_nn_distances": np.round(nn, 4).tolist(),
            "threshold": float(np.nanpercentile(nn, OOD_PERCENTILE)), "percentile": OOD_PERCENTILE}


# --------------------------------------------------------------------------- #
# Train + save
# --------------------------------------------------------------------------- #
def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def train(n_bootstrap: int = N_BOOTSTRAP, verbose: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    pts = load_points_v2()
    y = pts["burn"].to_numpy(dtype=int)
    fam = pts["material_family"].to_numpy()
    results, oof, per_family = {}, {}, {}
    for name in MODEL_LABELS:
        oof[name] = loto_oof(name, pts)
        results[name] = {"label": MODEL_LABELS[name], **score(y, oof[name])}
        per_family[name] = {f: score(y[fam == f], oof[name][fam == f]) for f in FAMILIES if (fam == f).any()}
        if verbose:
            r = results[name]
            print(f"{name:9} acc={r['accuracy']:.3f} bal={r['balanced_accuracy']} brier={r['brier']:.3f} "
                  f"logloss={r['log_loss']:.3f} auc={r['auc']}")
    candidates = [n for n in MODEL_LABELS if n != "baseline"]
    best = min(candidates, key=lambda n: results[n]["brier"])
    chosen = best if results[best]["brier"] < results["baseline"]["brier"] else "logreg"

    # Sensitivity: high-confidence points only (LOTO on those points) vs high+medium scored on the same points.
    hi = pts[pts["label_confidence"] == "high"].reset_index(drop=True)
    sens = {}
    for name in candidates:
        p_hi = loto_oof(name, hi)
        mask = (pts["label_confidence"] == "high").to_numpy()
        sens[name] = {"trained_on_high_only": score(hi["burn"].to_numpy(), p_hi),
                      "trained_on_high_and_medium_scored_on_high": score(y[mask], oof[name][mask])}

    stress = {name: lomo_stress(name, pts) for name in candidates}
    finals = {name: fit(name, pts) for name in candidates}
    mono = {name: monotonicity(finals[name], pts) for name in candidates}
    final = finals[chosen]
    boots, redrawn = bootstrap_models(chosen, pts, n_bootstrap)
    dist = distance_space(pts, final.stats)
    env = family_envelopes(pts)

    # v1 points: score v2's out-of-fold predictions on the 21 v1 points (same test, flow and O2).
    v1 = pd.read_csv(ROOT / "data" / "processed" / "flame_points.csv")
    key = lambda d: list(zip(d["test_id"].astype(str), d["flow_cm_s"].round(3), d["o2_pct"].round(2), d["burn"]))  # noqa: E731
    k1, k2 = set(key(v1)), key(pts)
    m_v1 = np.array([k in k1 for k in k2])
    on_v1 = {name: score(y[m_v1], oof[name][m_v1]) for name in MODEL_LABELS}
    sibal = fam == "SIBAL_fabric"

    po = oof[chosen]
    metrics = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        "engine_version": "v2",
        "data": {
            "points_file": str(POINTS_V2.relative_to(ROOT)), "points_sha256": _sha256(POINTS_V2),
            "source": "NASA/TM-20210011385: Appendix A Tables A.1-A.6 (all BASS-II tests), Table 7.1 (SIBAL), Table 5.1 (Miller)",
            "n_points": int(len(pts)), "n_tests": int(pts["test_id"].nunique()),
            "class_balance": {"burn": int(y.sum()), "extinguished": int(len(y) - y.sum())},
            "label_confidence": pts["label_confidence"].value_counts().to_dict(),
            "families": {f: env[f] for f in FAMILIES},
            "catalog_tests": 126,
        },
        "features": {name: MODEL_FEATURES[name] for name in MODEL_LABELS},
        "validation": "leave-one-test-out (LeaveOneGroupOut grouped by test_id)",
        "models": results,
        "per_family": per_family,
        "selection_rule": "lowest LOTO Brier score; if none beats the baseline, ship logreg",
        "chosen_model": chosen, "chosen_beats_baseline": bool(results[chosen]["brier"] < results["baseline"]["brier"]),
        "selection_note": f"Lowest LOTO Brier: {best} ({results[best]['brier']}) vs baseline ({results['baseline']['brier']}).",
        "calibration_oof": {"model": chosen, "table": reliability_table(y, po),
                            "mean_predicted_p_burn": round(float(po.mean()), 3), "observed_burn_rate": round(float(y.mean()), 3)},
        "stress_test_leave_one_family_out": stress,
        "monotonicity_check": mono,
        "sensitivity_high_confidence_only": sens,
        "on_v1_points": {"n_points": int(m_v1.sum()), "models": on_v1,
                         "note": "v2 out-of-fold predictions (trained on all families) scored on the 21 v1 SIBAL points"},
        "sibal_subset": {name: score(y[sibal], oof[name][sibal]) for name in MODEL_LABELS},
        "bootstrap": {"unit": "test", "n_resamples": n_bootstrap, "single_class_resamples_redrawn": redrawn,
                      "interval_level": INTERVAL_LEVEL, "seed": SEED,
                      "extrapolation_rule": "where the kNN check flags an extrapolation, the API reports the interval as [0, 1]"},
        "ood": {"hard_rules": "material in data; pressure 14.7 +/- 0.3 psia; microgravity; configuration seen for the family; "
                              "O2, flow, thickness and size inside the family's training ranges",
                "knn_features": DIST_FEATURES, "knn_scope": "nearest training point of the same material family",
                "knn_percentile": OOD_PERCENTILE, "knn_threshold": round(dist["threshold"], 3),
                "loto_nn_distances": dist["loto_nn_distances"]},
        "environment": {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
                        "numpy": np.__version__, "pandas": pd.__version__},
        "artifact_version": ARTIFACT_VERSION,
    }
    artifact = {
        "artifact_version": ARTIFACT_VERSION, "sklearn_version": sklearn.__version__, "chosen_model": chosen,
        "model_label": MODEL_LABELS[chosen], "final_model": final, "bootstrap_models": boots,
        "interval_level": INTERVAL_LEVEL, "distance": dist, "envelopes": env, "size_stats": final.stats,
        "points": pts.to_dict(orient="records"), "loto_oof": {k: v.round(4).tolist() for k, v in oof.items()},
        "metrics": metrics,
    }
    if verbose:
        print(metrics["selection_note"], "chosen:", chosen)
        print("monotonicity:", mono)
        print(f"kNN threshold {dist['threshold']:.3f}; bootstrap {n_bootstrap} (redrawn {redrawn})")
    return artifact, metrics


def history(metrics_v2: dict[str, Any]) -> dict[str, Any]:
    v1 = json.loads(METRICS_V1.read_text(encoding="utf-8"))
    c1, c2 = v1["chosen_model"], metrics_v2["chosen_model"]
    pick = lambda r: {k: r.get(k) for k in ("accuracy", "balanced_accuracy", "brier", "log_loss", "auc", "n_points")}  # noqa: E731
    return {
        "note": "LOTO metrics. v1 = 21 SIBAL points from 12 tests (Table 7.1). v2 = all BASS-II families "
                "(Appendix A + Tables 7.1 and 5.1). 'v2 on the v1 points' scores v2's out-of-fold predictions on the same 21 points.",
        "v1": {"chosen_model": c1, "n_points": v1["data"]["n_points"], "n_tests": v1["data"]["n_tests"], "materials": ["SIBAL_fabric"],
               "baseline": pick(v1["models"]["baseline"]), "chosen": pick(v1["models"][c1])},
        "v2": {"chosen_model": c2, "n_points": metrics_v2["data"]["n_points"], "n_tests": metrics_v2["data"]["n_tests"],
               "materials": FAMILIES, "baseline": pick(metrics_v2["models"]["baseline"]), "chosen": pick(metrics_v2["models"][c2])},
        "v2_on_v1_points": {"baseline": pick(metrics_v2["on_v1_points"]["models"]["baseline"]),
                            "chosen": pick(metrics_v2["on_v1_points"]["models"][c2])},
    }


def save(artifact: dict[str, Any], metrics: dict[str, Any]) -> None:
    import joblib

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, ARTIFACT_V2, compress=3)
    METRICS_V2.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    HISTORY.write_text(json.dumps(history(metrics), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_artifact_v2(allow_retrain: bool = True) -> dict[str, Any]:
    """Load the saved v2 artifact; if missing or pickled by another scikit-learn version, retrain in-process."""
    import joblib

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            art = joblib.load(ARTIFACT_V2)
        if art.get("sklearn_version") == sklearn.__version__ and art.get("artifact_version") == ARTIFACT_VERSION:
            return art
    except Exception:  # noqa: BLE001
        if not allow_retrain:
            raise
    if not allow_retrain:
        raise RuntimeError("artifact version mismatch")
    return runtime_artifact()


def runtime_artifact(n_bootstrap: int = 200) -> dict[str, Any]:
    """Fast in-process rebuild of the shipped model only (no model comparison): the chosen model named in
    metrics_v2.json, its bootstrap and the OOD tables, with the same seeds. Used when the pickled artifact
    cannot be loaded (e.g. a different scikit-learn version on the server)."""
    metrics = json.loads(METRICS_V2.read_text(encoding="utf-8"))
    chosen = metrics["chosen_model"]
    pts = load_points_v2()
    final = fit(chosen, pts)
    boots, _ = bootstrap_models(chosen, pts, n_bootstrap)
    return {
        "artifact_version": ARTIFACT_VERSION, "sklearn_version": sklearn.__version__, "chosen_model": chosen,
        "model_label": MODEL_LABELS[chosen], "final_model": final, "bootstrap_models": boots,
        "interval_level": INTERVAL_LEVEL, "distance": distance_space(pts, final.stats), "envelopes": family_envelopes(pts),
        "size_stats": final.stats, "points": pts.to_dict(orient="records"), "metrics": metrics, "retrained_at_load": True,
    }


def main() -> None:
    art, metrics = train()
    save(art, metrics)
    print(f"Saved {ARTIFACT_V2.relative_to(ROOT)} ({ARTIFACT_V2.stat().st_size / 1024:.0f} KB), "
          f"{METRICS_V2.relative_to(ROOT)}, {HISTORY.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
