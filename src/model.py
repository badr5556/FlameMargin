"""FlameMargin Prediction Engine (Layer 1): training, validation and the saved artifact.

Train and write ``models/flame_model.joblib`` + ``models/metrics.json``:

    python -m src.model

What it does (all choices are documented in docs/model_card.md):
  1. Loads the 21 derived observation points (12 NASA tests, SIBAL fabric,
     NASA/TM-20210011385 Table 7.1).
  2. Compares three pre-specified models with leave-one-test-out validation
     (LeaveOneGroupOut grouped by test_id, so both points of a test stay together):
       - baseline: majority class (DummyClassifier strategy="prior": predicts the
         majority label of the training fold, probability = training class rate)
       - logreg:   L2 logistic regression on standardized features
       - gpc:      GaussianProcessClassifier, ConstantKernel*RBF + WhiteKernel,
                   standardized features
     A Gaussian process with one length scale per feature (ARD) is also scored as a
     sensitivity check; it is reported but not eligible for selection.
  3. Picks the eligible model with the lowest LOTO Brier score. If none beats the
     baseline, it says so and ships the logistic regression (most interpretable).
  4. Bootstraps the chosen model over tests (resample the 12 tests with
     replacement, 300 times) for a 90% interval on P(burn).
  5. Fits the kNN out-of-distribution threshold: the 95th percentile of the
     leave-one-test-out nearest-neighbour distances in standardized
     (o2_pct, log10_flow, sample_width_cm) space.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import warnings
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from src.features import DISTANCE_FEATURES, FEATURES, POINTS_CSV, ROOT, feature_frame, load_points, training_matrix

MODELS_DIR = ROOT / "models"
ARTIFACT_PATH = MODELS_DIR / "flame_model.joblib"
METRICS_PATH = MODELS_DIR / "metrics.json"

SEED = 42
N_BOOTSTRAP = 300
INTERVAL_LEVEL = 0.90
OOD_PERCENTILE = 95.0
ARTIFACT_VERSION = "1.0"

MODEL_LABELS = {
    "baseline": "Majority-class baseline",
    "logreg": "Logistic regression (L2, standardized)",
    "gpc": "Gaussian process classifier (RBF + White, standardized)",
    "gpc_ard": "Gaussian process classifier, ARD RBF (sensitivity only)",
}
ELIGIBLE = ("baseline", "logreg", "gpc")


def _make(name: str) -> Pipeline | DummyClassifier:
    if name == "baseline":
        return DummyClassifier(strategy="prior")
    if name == "logreg":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))
    if name == "gpc":
        kernel = ConstantKernel(1.0) * RBF(length_scale=1.0) + WhiteKernel(noise_level=1e-2)
        return make_pipeline(StandardScaler(), GaussianProcessClassifier(kernel=kernel, n_restarts_optimizer=2, random_state=0))
    if name == "gpc_ard":
        kernel = ConstantKernel(1.0) * RBF(length_scale=np.ones(len(FEATURES))) + WhiteKernel(noise_level=1e-2)
        return make_pipeline(StandardScaler(), GaussianProcessClassifier(kernel=kernel, n_restarts_optimizer=2, random_state=0))
    raise KeyError(name)


def _fit(name: str, X: pd.DataFrame, y: np.ndarray):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        return _make(name).fit(X, y)


def _proba(model, X: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(X[FEATURES])[:, 1]


def bootstrap_interval(boots: list[Any], X: pd.DataFrame, level: float = INTERVAL_LEVEL) -> tuple[np.ndarray, np.ndarray]:
    """Central ``level`` percentile band of the replicates' P(burn) (bootstrap over tests).

    Caveat (handled in src/api.py): far from the data every GP replicate reverts to its
    prior, P(burn) = 0.5, so this band collapses to [0.5, 0.5] there. A collapsed band
    would look certain when the model has no information, so the API reports [0, 1]
    wherever the kNN check flags an extrapolation.
    """
    B = np.vstack([_proba(b, X) for b in boots])
    a = (1 - level) / 2
    return np.quantile(B, a, axis=0), np.quantile(B, 1 - a, axis=0)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def loto_predictions(name: str, X: pd.DataFrame, y: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Out-of-fold P(burn) for every point, holding out one test at a time."""
    p = np.zeros(len(y), dtype=float)
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        p[te] = _proba(_fit(name, X.iloc[tr], y[tr]), X.iloc[te])
    return p


def score(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    yhat = (p >= 0.5).astype(int)
    return {
        "accuracy": round(float(accuracy_score(y, yhat)), 3),
        "balanced_accuracy": round(float(balanced_accuracy_score(y, yhat)), 3),
        "brier": round(float(brier_score_loss(y, p)), 3),
        "log_loss": round(float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1])), 3),
        "n_points": int(len(y)),
    }


# --------------------------------------------------------------------------- #
# Bootstrap over tests
# --------------------------------------------------------------------------- #
def bootstrap_models(name: str, X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, n: int = N_BOOTSTRAP, seed: int = SEED) -> tuple[list[Any], int]:
    """Refit ``name`` on ``n`` resamples of whole tests. Resamples with one class are redrawn (counted)."""
    rng = np.random.default_rng(seed)
    tests = np.unique(groups)
    idx_by_test = {t: np.flatnonzero(groups == t) for t in tests}
    fitted, redrawn = [], 0
    while len(fitted) < n:
        pick = rng.choice(tests, size=len(tests), replace=True)
        idx = np.concatenate([idx_by_test[t] for t in pick])
        if len(np.unique(y[idx])) < 2:
            redrawn += 1
            continue
        fitted.append(_fit(name, X.iloc[idx].reset_index(drop=True), y[idx]))
    return fitted, redrawn


# --------------------------------------------------------------------------- #
# kNN distance (out-of-distribution)
# --------------------------------------------------------------------------- #
def distance_space(points: pd.DataFrame) -> dict[str, Any]:
    D = feature_frame(points["o2_pct"], points["flow_cm_s"], points["sample_width_cm"])[DISTANCE_FEATURES].to_numpy()
    mu, sd = D.mean(axis=0), D.std(axis=0)
    Z = (D - mu) / sd
    groups = points["test_id"].to_numpy(dtype=str)
    nn = np.array([np.min(np.linalg.norm(Z[groups != groups[i]] - Z[i], axis=1)) for i in range(len(Z))])
    return {
        "features": list(DISTANCE_FEATURES),
        "mean": mu.tolist(),
        "std": sd.tolist(),
        "train_z": Z,
        "loto_nn_distances": nn.round(4).tolist(),
        "threshold": float(np.percentile(nn, OOD_PERCENTILE)),
        "percentile": OOD_PERCENTILE,
    }


# --------------------------------------------------------------------------- #
# Monotonicity sanity check
# --------------------------------------------------------------------------- #
def monotonicity_report(predict: Callable[[pd.DataFrame], np.ndarray], flow_cm_s: float = 10.0, width: float = 2.2,
                        o2_lo: float = 16.4, o2_hi: float = 21.0, tol: float = 1e-3) -> dict[str, Any]:
    """Does P(burn) ever drop as O2 rises at a fixed mid-range flow? (It should not, physically.)"""
    o2 = np.round(np.arange(o2_lo, o2_hi + 1e-9, 0.1), 2)
    p = predict(feature_frame(o2, flow_cm_s, width))
    drops = np.flatnonzero(np.diff(p) < -tol)
    return {
        "flow_cm_s": flow_cm_s, "sample_width_cm": width, "o2_range": [o2_lo, o2_hi],
        "violated": bool(len(drops)),
        "first_drop_at_o2": float(o2[drops[0]]) if len(drops) else None,
        "max_drop": round(float(-np.min(np.diff(p))), 3) if len(drops) else 0.0,
        "p_at_o2_lo": round(float(p[0]), 3), "p_peak": round(float(p.max()), 3),
        "o2_at_peak": float(o2[int(np.argmax(p))]), "p_at_o2_hi": round(float(p[-1]), 3),
    }


# --------------------------------------------------------------------------- #
# Train + save
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train(n_bootstrap: int = N_BOOTSTRAP, verbose: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (artifact, metrics). Deterministic for a given scikit-learn version."""
    points = load_points()
    X, y, groups = training_matrix(points)
    results, oof = {}, {}
    for name in MODEL_LABELS:
        oof[name] = loto_predictions(name, X, y, groups)
        results[name] = {"label": MODEL_LABELS[name], "eligible": name in ELIGIBLE, **score(y, oof[name])}
        if verbose:
            r = results[name]
            print(f"{name:9} acc={r['accuracy']:.3f} bal_acc={r['balanced_accuracy']:.3f} brier={r['brier']:.3f} log_loss={r['log_loss']:.3f}")

    base = results["baseline"]["brier"]
    candidates = [n for n in ELIGIBLE if n != "baseline"]
    best = min(candidates, key=lambda n: results[n]["brier"])
    beats = results[best]["brier"] < base
    chosen = best if beats else "logreg"
    selection_note = (
        f"Lowest LOTO Brier among eligible models: {best} ({results[best]['brier']}) vs baseline ({base})."
        if beats else
        f"No eligible model beat the baseline Brier ({base}); shipping the most interpretable model (logreg)."
    )

    final = _fit(chosen, X, y)
    boots, redrawn = bootstrap_models(chosen, X, y, groups, n_bootstrap)
    dist = distance_space(points)

    mono = {
        name: monotonicity_report(lambda F, m=_fit(name, X, y): _proba(m, F))
        for name in ("logreg", "gpc")
    }
    mono["chosen"] = mono.get(chosen) or monotonicity_report(lambda F: _proba(final, F))

    final_kernel = None
    if hasattr(final, "steps") and hasattr(final.steps[-1][1], "kernel_"):
        final_kernel = str(final.steps[-1][1].kernel_)
    coef = None
    if chosen == "logreg":
        lr = final.steps[-1][1]
        coef = {"intercept": round(float(lr.intercept_[0]), 4), **{f: round(float(c), 4) for f, c in zip(FEATURES, lr.coef_[0])}}

    # Calibration summary of the chosen model's out-of-fold predictions (too few points for a reliability diagram).
    po = oof[chosen]
    calib = {
        "mean_predicted_p_burn": round(float(po.mean()), 3), "observed_burn_rate": round(float(y.mean()), 3),
        "mean_p_when_burn": round(float(po[y == 1].mean()), 3), "mean_p_when_extinguished": round(float(po[y == 0].mean()), 3),
        "share_of_oof_predictions_within_0.4_0.6": round(float(np.mean(np.abs(po - 0.5) <= 0.1)), 3),
    }
    # Bootstrap replicates whose GP length-scale collapsed (memorizes points, reverts to 0.5 between them).
    short_ls = None
    if chosen.startswith("gpc"):
        ls = []
        for b in boots:
            k = b.steps[-1][1].kernel_
            ls.append(float(np.min(np.atleast_1d(k.k1.k2.length_scale))))
        short_ls = round(float(np.mean(np.asarray(ls) < 0.05)), 3)

    n1 = int(y.sum())
    metrics = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        "data": {
            "points_file": str(POINTS_CSV.relative_to(ROOT)),
            "points_sha256": _sha256(POINTS_CSV),
            "source": "NASA/TM-20210011385, Section 7.1, Table 7.1 (BASS-II, SIBAL cotton-fiberglass fabric, ISS, 1 atm, concurrent flow)",
            "n_points": int(len(y)), "n_tests": int(len(np.unique(groups))),
            "class_balance": {"burn": n1, "extinguished": int(len(y) - n1)},
            "row_verification": "PENDING (docs/data/verification_checklist.md)",
        },
        "features": FEATURES,
        "validation": "leave-one-test-out (LeaveOneGroupOut grouped by test_id; both points of a test held out together)",
        "models": results,
        "selection_rule": "lowest LOTO Brier score among eligible models; if none beats the baseline, ship logreg",
        "chosen_model": chosen,
        "chosen_beats_baseline": bool(beats),
        "selection_note": selection_note,
        "final_model": {"kernel": final_kernel, "logreg_coefficients_standardized": coef},
        "calibration_oof": calib,
        "bootstrap": {"unit": "test", "n_resamples": n_bootstrap, "single_class_resamples_redrawn": redrawn,
                      "interval_level": INTERVAL_LEVEL, "seed": SEED,
                      "share_of_replicates_with_length_scale_below_0.05": short_ls,
                      "extrapolation_rule": "where the kNN check flags an extrapolation, the API reports the interval as [0, 1]"},
        "ood": {
            "hard_rules": "material, pressure (14.7±0.3 psia), gravity (microgravity), O2 16.4–21.0%, flow 2.0–53 cm/s, sample width 1.2–2.2 cm",
            "knn_features": dist["features"], "knn_percentile": OOD_PERCENTILE,
            "knn_threshold": round(dist["threshold"], 3),
            "loto_nn_distances": dist["loto_nn_distances"],
        },
        "monotonicity_check": mono,
        "environment": {"python": platform.python_version(), "scikit_learn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
        "artifact_version": ARTIFACT_VERSION,
    }
    artifact = {
        "artifact_version": ARTIFACT_VERSION,
        "sklearn_version": sklearn.__version__,
        "chosen_model": chosen,
        "model_label": MODEL_LABELS[chosen],
        "features": FEATURES,
        "final_model": final,
        "bootstrap_models": boots,
        "interval_level": INTERVAL_LEVEL,
        "distance": dist,
        "points": points.to_dict(orient="records"),
        "loto_oof": {k: v.round(4).tolist() for k, v in oof.items()},
        "metrics": metrics,
    }
    if verbose:
        print(selection_note)
        print(f"Chosen: {chosen}; bootstrap resamples: {n_bootstrap} (redrawn {redrawn}); kNN threshold {dist['threshold']:.3f}")
        print(f"Monotonicity ({chosen}): violated={mono['chosen']['violated']} first drop at O2={mono['chosen']['first_drop_at_o2']}")
    return artifact, metrics


def save(artifact: dict[str, Any], metrics: dict[str, Any]) -> None:
    import joblib

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, ARTIFACT_PATH, compress=3)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_artifact(allow_retrain: bool = True) -> dict[str, Any]:
    """Load the saved artifact. If it is missing or was pickled by another scikit-learn
    version, retrain in-process with the same seeds (does not overwrite the files)."""
    import joblib

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # InconsistentVersionWarning -> retrain
            art = joblib.load(ARTIFACT_PATH)
        if art.get("sklearn_version") == sklearn.__version__ and art.get("artifact_version") == ARTIFACT_VERSION:
            return art
    except Exception:  # noqa: BLE001 - any load problem -> deterministic retrain
        if not allow_retrain:
            raise
    if not allow_retrain:
        raise RuntimeError("artifact version mismatch")
    art, _ = train(verbose=False)
    art["retrained_at_load"] = True
    return art


def main() -> None:
    artifact, metrics = train()
    save(artifact, metrics)
    size_kb = ARTIFACT_PATH.stat().st_size / 1024
    print(f"Saved {ARTIFACT_PATH.relative_to(ROOT)} ({size_kb:.0f} KB) and {METRICS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
