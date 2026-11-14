"""Labelled observation points v2: rule-based, multi-material and fully traceable.

Input
    data/raw/bass2_appendix_a_tests.csv   126 BASS-II tests (Appendix A, Tables A.1-A.6)
    Table 7.1 (p. 96) and Table 5.1 (p. 57) parsed from the committed page-text snapshot
Output
    data/processed/flame_points_v2.csv    one row per (test, flow, outcome) observation

Every point carries ``derivation_rule``, ``label_confidence``, a verbatim ``evidence_quote`` (an exact
substring of the test's Appendix A observation text, or of the whitespace-normalized page text for
Table 7.1 / Table 5.1 / report text) and the printed ``source_page``.

Rules (one name per case; each is a function below and is unit-tested with real quotes)
    stated_burning_at_flow            burn=1 high    text says steady burning / spread / stable flame at a
                                                     cm/s value, or at multiple / decreasing flows (then every
                                                     air-display cm/s value before the extinction step)
    stated_extinction_at_flow         burn=0 high    text gives the cm/s at extinction or blowoff (O2 = calibrated final)
    no_sustained_ignition             burn=0 high    no ignition / not sustained, at the single test flow
                                                     (one point per cm/s only if the text says "at any flow")
    no_blowoff_at_max                 burn=1 high    no blowoff at the maximum STATED cm/s
    hedged_burning                    burn=1 medium  hedged wording ("seemed to burn ...", "still did not extinguish")
    flame_present_before_ramp         burn=1 medium  a flame existed and the flow was then changed until an
                                                     extinction / blowoff / end of test: every air-display cm/s
                                                     value before that step (added rule, see extraction_audit.md)
    table_5_1_spread_rate_at_flow     burn=1 high    Table 5.1 reports a measured spread rate at this velocity
    text_reports_steady_spread__unique_condition_match
                                      burn=1 high    report text (p. 95) describes steady spread for a condition
                                                     that matches exactly one Table 7.1 test
    v1_flame_before_ramp              burn=1 high    SIBAL v1 rule R1/R2/R3 start point (Table 7.1 outcome explicit)
    v1_quenched_end / v1_no_ignition  burn=0 high    SIBAL v1 rules R1 end / R4 when no A.6 sentence gives the flow

O2: burn points use the calibrated initial O2, extinction points the calibrated final O2 (Appendix A);
SIBAL points use the Table 7.1 O2 (one value per test); Table 5.1 points use its initial O2.

Run from the repo root:
    python -m src.data_pipeline.derive_points_v2
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from src.data_pipeline.extract_appendix_a import CATALOG_CSV, normalize_ws
from src.data_pipeline.report_tables import page_text, parse_table_5_1, parse_table_7_1

ROOT = Path(__file__).resolve().parents[2]
OUT_POINTS = ROOT / "data" / "processed" / "flame_points_v2.csv"

POINT_COLUMNS = [
    "point_id", "test_id", "pi_table", "material_family", "thickness_mm", "width_cm", "diameter_mm",
    "flow_configuration", "o2_pct", "flow_cm_s", "burn", "label_confidence", "derivation_rule",
    "evidence_quote", "source_page", "include_in_training",
    # provenance extras
    "exclusion_reason", "appendix_test_id", "pi", "pmma_color", "sides_burning", "o2_source", "conditions_source",
]

SIBAL_THICKNESS_MM = 0.32  # p. 94: "The thickness of the sample is about 0.32 mm"
SIBAL_THICKNESS_QUOTE = "The thickness of the sample is about 0.32 mm"

_N = r"(\d+(?:\.\d+)?)"


# --------------------------------------------------------------------------- #
# Air-display parsing
# --------------------------------------------------------------------------- #
# Rows whose "Air display" cell holds fan-display readings with the cm/s values in parentheses
# (or written as "N cm/s"). The cm/s values below are the ones printed in that same cell.
AIR_DISPLAY_CMS_OVERRIDE: dict[str, tuple[list[Any], str]] = {
    "O13a": ([5.0, 2.0, 0.0], "cell '49, 44, 42, 41, 41, 40.5 (5, 2, 0)': numbers outside the parentheses are fan readings; cm/s in parentheses"),
    "O13b": ([7.0], "cell '7, 4? (49, ?)': 4? is uncertain and not used"),
    "O5b": ([5.0], "cell '49, 5 cm/s': 49 is a fan reading, 5 is written with its unit"),
}

EXTINCTION_MARKERS = ("extinction", "extinguished", "blowoff", "blow-off", "off", "low", "lower", "decrease")
MAX_MARKERS = ("max", "maximum")


@dataclass
class AirToken:
    text: str
    value: float | None  # cm/s, or None for markers / pots / uncertain values
    kind: str  # "cms" | "pot" | "marker" | "max" | "uncertain"


def parse_air_display(raw: str, test_id: str = "") -> list[AirToken]:
    """Split an Air display cell into cm/s values and markers (verbatim tokens kept)."""
    if test_id in AIR_DISPLAY_CMS_OVERRIDE:
        return [AirToken(f"{v:g}", v, "cms") for v in AIR_DISPLAY_CMS_OVERRIDE[test_id][0]]
    s = str(raw or "")
    s = re.sub(r"\b(max(?:imum)?) \((\d+(?:\.\d+)?)\)", r"\1=\2", s)  # "maximum (47)" -> max value 47
    s = re.sub(r"\([^)]*\)", " ", s)  # parenthetical pot lists are not cm/s
    s = s.replace(">", ",")
    tokens: list[AirToken] = []
    pots_mode = False
    for part in [p.strip() for p in s.split(",") if p.strip()]:
        low = part.lower()
        if m := re.fullmatch(r"(max|maximum)=(\d+(?:\.\d+)?)", low):
            tokens.append(AirToken(part, float(m.group(2)), "max"))
            continue
        if "pot" in low:
            pots_mode = low.startswith("pots") or pots_mode
            tokens.append(AirToken(part, None, "pot"))
            continue
        if pots_mode and re.fullmatch(r"\.?\d+(\.\d+)?", low):
            tokens.append(AirToken(part, None, "pot"))
            continue
        if re.search(r"[~?<]|approaching", low):
            tokens.append(AirToken(part, None, "uncertain"))
            continue
        if m := re.fullmatch(r"(\d+(?:\.\d+)?)(?: cm/s)?(?: (ignition|ibid|decrease|down to extinction|down then blowoff|extinction))?", low):
            tokens.append(AirToken(part, float(m.group(1)), "cms"))
            if m.group(2) and m.group(2) not in ("ignition", "ibid"):
                tokens.append(AirToken(m.group(2), None, "marker"))
            continue
        if low in MAX_MARKERS:
            tokens.append(AirToken(part, None, "max"))
            continue
        if any(k in low for k in EXTINCTION_MARKERS):
            tokens.append(AirToken(part, None, "marker"))
            continue
        tokens.append(AirToken(part, None, "uncertain"))
    return tokens


def cms_values(tokens: list[AirToken]) -> list[float]:
    return [t.value for t in tokens if t.kind in ("cms", "max") and t.value is not None]


def flows_before_extinction(tokens: list[AirToken], extinction_flow: float | None = None,
                            drop_ambiguous_last: bool = False) -> list[float]:
    """cm/s values (> 0, certain) listed before the first extinction marker, without the stated
    extinction flow. ``drop_ambiguous_last``: also drop the last value when the extinction step has no
    cm/s and no marker separates it (the last reading may be the extinction step itself)."""
    out: list[float] = []
    saw_marker = False
    for t in tokens:
        if t.kind == "marker" or (t.kind == "max" and t.value is None):
            saw_marker = True
            break
        if t.kind == "cms" and t.value:
            out.append(t.value)
    if extinction_flow is not None:
        out = [v for v in out if v != extinction_flow]
    elif drop_ambiguous_last and not saw_marker and out and tokens and tokens[-1].kind == "cms" and tokens[-1].value == out[-1]:
        # the list ends on this reading and the extinction followed it: it may be the extinction step itself
        last = out[-1]
        out = [v for v in out if v != last]
    return _unique(out)


def _unique(vals: list[float]) -> list[float]:
    seen, out = set(), []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


# --------------------------------------------------------------------------- #
# Quotes
# --------------------------------------------------------------------------- #
def clause_quote(text: str, m: re.Match, max_len: int = 220) -> str:
    """The ';'-delimited clause that contains the match (an exact substring of ``text``)."""
    start = text.rfind(";", 0, m.start()) + 1
    end = text.find(";", m.end())
    end = len(text) if end < 0 else end
    q = text[start:end].strip()
    if len(q) > max_len:
        q = m.group(0).strip()
    return q


# --------------------------------------------------------------------------- #
# Rule classifiers (pure functions on the observation text)
# --------------------------------------------------------------------------- #
@dataclass
class Hit:
    rule: str
    quote: str
    flows: list[float] = field(default_factory=list)  # flows stated in the quote itself
    mode: str = "quote"  # "quote" | "air_before_extinction" | "air_single" | "air_max" | "air_any"
    confidence: str = "high"


def _find(patterns: list[tuple[str, str]], text: str, rule: str, confidence: str = "high") -> list[Hit]:
    hits = []
    for pat, mode in patterns:
        for m in re.finditer(pat, text):
            flows = [float(g) for g in m.groups() if g is not None and re.fullmatch(r"\d+(\.\d+)?", g)]
            hits.append(Hit(rule, clause_quote(text, m), flows, mode, confidence))
    return hits


# stated_burning_at_flow: flows written in the quote
BURN_EXPLICIT = [
    (rf"Steady burning at {_N}(?: and {_N})? cm/s", "quote"),                    # B6, B9
    (rf"\bSpread at {_N} cm/s", "quote"),                                         # B8, B15
    (rf"flame spread whole sample at {_N} cm/s", "quote"),                        # T16
    (rf"(?<!after )\b\d+(?:\.\d+)? min at {_N} cm/s", "quote"),                   # O15a "1.5 min at 5 cm/s"
    (rf"ignition at {_N} cm/s \(left \d+ min\)", "quote"),                        # M20
    (rf"turned flow up to {_N} cm/s and got steady spreading there", "quote"),    # M15
    (rf"flow briefly at {_N} cm/s but flame was too strong", "quote"),           # M18
    (rf"Ignite at {_N} cm/s, turn down to \d+ cm/s after spread away from igniter", "quote"),  # M2
    (rf"very slow propagation; changed flow from {_N} to {_N} cm/s", "quote"),   # M1
    (rf"targeted constant flows of {_N}, {_N}, and {_N}", "quote"),              # M17
]
# stated_burning_at_flow: flows = air-display cm/s before the extinction step
BURN_MULTI = [
    r"Multiple velocities for steady spread", r"steady burn at multiple velocities", r"multiple steady spread flows",
    r"Burned with decreasing flows", r"Burned at decreasing flow", r"burned entire sample",
    r"multiple flows for steady spreading", r"steady at multiple pots", r"steady burning until turned flow off",
    r"flame persisted for all", r"Nice stable burn at low velocity", r"but steady spread",
    r"Burned steadily at higher flows", r"holding constant for 6 min at pot settings",
    r"Ignited and burned at 5 pot settings",
]
# stated_burning_at_flow at the single flow of the test
BURN_SINGLE = [r"Burned completely, steady", r"^Steady burn\b", r"^Nice stable burn\b", r"turned flow off after spread halfway"]


def stated_burning_hits(text: str) -> list[Hit]:
    hits = _find(BURN_EXPLICIT, text, "stated_burning_at_flow")
    hits += _find([(p, "air_before_extinction") for p in BURN_MULTI], text, "stated_burning_at_flow")
    hits += _find([(p, "air_single") for p in BURN_SINGLE], text, "stated_burning_at_flow")
    return hits


EXTINCTION_EXPLICIT = [
    rf"self-extinguished at an air reading of {_N} cm/s",                         # M14
    rf"\bextinguished {_N} cm/s",                                                  # M18
    rf"went out on its own at {_N} cm/s",                                          # M19
    rf"(?<!self-)\b[Ee]xtinguished at {_N} cm/s",                                  # M3, M11, M5
    rf"self-extinguished at {_N} cm/s",                                            # M10, P21a
    rf"Quick extinction when we turned air down to {_N} cm/s",                     # T20
    rf"died after \d+ min at {_N} cm/s",                                           # M9
    rf"flow down to {_N} cm/s \(flame out after",                                  # M20
    rf"increased flow to {_N} cm/s, but it self-extinguished",                     # M2
    rf"turned down to {_N} and extinguished",                                      # T22
]
EXTINCTION_MEDIUM = [rf"turned down flow to {_N} and got spreading and slow extinction there"]  # M15
BLOWOFF_AT_MAX = [r"Successful blowoff"]                                           # T21, flow = max of air display


def stated_extinction_hits(text: str) -> list[Hit]:
    hits = _find([(p, "quote") for p in EXTINCTION_EXPLICIT], text, "stated_extinction_at_flow")
    hits += _find([(p, "quote") for p in EXTINCTION_MEDIUM], text, "stated_extinction_at_flow", "medium")
    hits += _find([(p, "air_max") for p in BLOWOFF_AT_MAX], text, "stated_extinction_at_flow")
    return hits


NO_IGNITION = [
    r"did not spread at all and extinguished", r"flame would not sustain", r"[Nn]o sustained flame(?: at any flow)?",
    r"[Bb]rief ignition but flame extinguished before spreading beyond igniter", r"no joy on sustained flame",
    r"[Dd]id not ignite", r"would not stay lit", r"[Ww]ould not sustain a flame", r"only brief ignition, flame extinguished",
    r"brief flames go out", r"flame only briefly flashed then went out",
]


def no_sustained_ignition_hits(text: str) -> list[Hit]:
    hits = []
    for pat in NO_IGNITION:
        for m in re.finditer(pat, text):
            any_flow = "at any flow" in m.group(0) or "at any flow" in text
            hits.append(Hit("no_sustained_ignition", clause_quote(text, m), [], "air_any" if any_flow else "air_single"))
    return hits


NO_BLOWOFF = [r"did not blowoff", r"no blowoff attained", r"Tried to blowoff, but did not", r"tried blowoff without success"]


def no_blowoff_hits(text: str) -> list[Hit]:
    return _find([(p, "air_max") for p in NO_BLOWOFF], text, "no_blowoff_at_max")


HEDGED = [
    (r"seemed to burn full sample length as a flamelet", "air_before_extinction"),           # T5
    (r"still did not extinguish", "air_before_extinction"),                                   # T6
    (rf"turn down to {_N} cm/s after spread away from igniter; seemed steady", "quote"),     # M2
]


def hedged_burning_hits(text: str) -> list[Hit]:
    hits = []
    for pat, mode in HEDGED:
        for m in re.finditer(pat, text):
            flows = [float(g) for g in m.groups() if g]
            # quote the hedged words themselves, not only the clause
            hits.append(Hit("hedged_burning", m.group(0) if mode == "quote" else clause_quote(text, m), flows, mode, "medium"))
    return hits


FLAME_EVENT = re.compile(
    r"extinguish|extinction|quench|blew out|blowoff|blow off|flame out|went out|out at|died|"
    r"once flame settled down|flame reached end of sample", re.I)


def flame_present_hit(text: str) -> Hit | None:
    """A flame existed (an extinction/blowoff/quench or end-of-test event is reported)."""
    m = FLAME_EVENT.search(text)
    if not m:
        return None
    return Hit("flame_present_before_ramp", clause_quote(text, m), [], "air_before_extinction_ambiguous", "medium")


# --------------------------------------------------------------------------- #
# Exclusions
# --------------------------------------------------------------------------- #
# Tests whose text is internally conflicting; no point is derived (reason in extraction_audit.md).
AMBIGUOUS_TESTS = {
    "O18": "flame blew out at the high-flow step, restabilized, then failed to restabilize at the same low flow it "
           "had burned at earlier; the outcome per flow is contradictory",
    "M12": "Appendix A air display '<1' (pot plateaus) but Table 5.1 lists velocities '12 and 10' (not tracked); "
           "the two sources disagree on the flows",
}
HARDWARE_ONLY = {
    "B2": "observations are about hardware only (camera cable, no stills)",
    "P21b": "observations are about hardware only (igniter broke); reused sample",
}


# --------------------------------------------------------------------------- #
# Point assembly
# --------------------------------------------------------------------------- #
@dataclass
class Point:
    test_id: str
    flow_cm_s: float
    burn: int
    o2_pct: float | None
    label_confidence: str
    derivation_rule: str
    evidence_quote: str
    source_page: int
    o2_source: str
    conditions_source: str
    exclusion_reason: str = ""


RULE_PRIORITY = [
    "table_5_1_spread_rate_at_flow", "stated_burning_at_flow", "stated_extinction_at_flow", "no_blowoff_at_max",
    "no_sustained_ignition", "text_reports_steady_spread__unique_condition_match", "v1_flame_before_ramp",
    "v1_quenched_end", "v1_no_ignition", "hedged_burning", "flame_present_before_ramp",
]


def _o2_ok(v: float | None) -> bool:
    return v is not None and not pd.isna(v) and 10.0 <= float(v) <= 30.0


def appendix_points(row: pd.Series) -> list[Point]:
    """Points for one non-SIBAL Appendix A test, from its observation text and air display."""
    text = str(row["observations_raw"] or "")
    tid = row["test_id"]
    tokens = parse_air_display(row["air_display_raw"], tid)
    single = cms_values(tokens)
    page = int(row["source_page"])
    ci, cf = row["cal_o2_initial"], row["cal_o2_final"]
    pts: list[Point] = []

    def add(flows, burn, hit: Hit, o2, o2_src):
        for f in flows:
            if f and f > 0:
                pts.append(Point(tid, float(f), burn, None if pd.isna(o2) else float(o2), hit.confidence, hit.rule,
                                 hit.quote, page, o2_src, f"Table {row['pi_table']} p. {page}"))

    ext_hits = stated_extinction_hits(text)
    ext_flow = None
    for h in ext_hits:
        flows = h.flows if h.mode == "quote" else ([max(single)] if single else [])
        if flows:
            ext_flow = flows[0]
        add(flows, 0, h, cf, "cal_o2_final")
    noign = no_sustained_ignition_hits(text)
    for h in noign:
        if h.mode == "air_any":
            add(single, 0, h, ci, "cal_o2_initial")
        elif len(single) == 1:
            add(single, 0, h, ci, "cal_o2_initial")
    burn_hits = stated_burning_hits(text)
    for h in burn_hits:
        if h.mode == "quote":
            add(h.flows, 1, h, ci, "cal_o2_initial")
        elif h.mode == "air_single":
            add(single if len(single) == 1 else [], 1, h, ci, "cal_o2_initial")
        else:
            add(flows_before_extinction(tokens, ext_flow), 1, h, ci, "cal_o2_initial")
    for h in no_blowoff_hits(text):
        nums = [t for t in tokens if t.kind in ("cms", "max")]
        open_max = any(t.kind == "max" and t.value is None for t in tokens)
        if nums and not open_max:
            add([max(t.value for t in nums if t.value is not None)], 1, h, ci, "cal_o2_initial")
    for h in hedged_burning_hits(text):
        add(h.flows if h.mode == "quote" else flows_before_extinction(tokens, ext_flow), 1, h, ci, "cal_o2_initial")
    if not noign:
        fp = flame_present_hit(text)
        if fp is not None:
            add(flows_before_extinction(tokens, ext_flow, drop_ambiguous_last=True), 1, fp, ci, "cal_o2_initial")
    return pts


def table_5_1_points(t51: pd.DataFrame) -> list[Point]:
    pts = []
    for _, r in t51.iterrows():
        if not r["spread_rate_tracked"]:
            continue
        for v in r["velocities_cm_s"]:
            pts.append(Point(r["test_id"], float(v), 1, float(r["o2_initial"]), "high", "table_5_1_spread_rate_at_flow",
                             r["row_text"], int(r["source_page"]), "Table 5.1 initial O2", "Table 5.1 p. 57"))
    return pts


# --------------------------------------------------------------------------- #
# SIBAL (Table 7.1 conditions + Table A.6 outcomes)
# --------------------------------------------------------------------------- #
def gmt_day(date_raw: str) -> int | None:
    """Day of year from 'GMT 100', 'GMT 2014-45' or, failing that, from the M/D date (non-leap year)."""
    s = str(date_raw or "")
    if m := re.search(r"GMT ?(?:\d{4}- ?)?(\d{1,3})\b", s):
        return int(m.group(1))
    if m := re.match(r"(\d{1,2})/(\d{1,2})/", s):
        mon, day = int(m.group(1)), int(m.group(2))
        cum = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
        return cum[mon - 1] + day
    return None


def match_table71_to_a6(t71: pd.DataFrame, cat: pd.DataFrame) -> dict[str, str]:
    """Table 7.1 'GMT<day>-T<n>' -> Table A.6 'T<n>' when the A.6 date has the same GMT day."""
    a6 = cat[cat["pi_table"] == "A.6"].copy()
    a6["day"] = a6["gmt_date_raw"].map(gmt_day)
    out = {}
    for tid in t71["test_id"]:
        day, num = re.match(r"GMT(\d+)-(T\d+[ab]?)", tid).groups()
        hit = a6[(a6["test_id"] == num) & (a6["day"] == int(day))]
        if len(hit) == 1:
            out[tid] = num
    return out


STEADY_SPREAD_TEXT = [  # p. 95, Figs. 7.2 / 7.3 discussion: contiguous spans from the condition to the steady-spread words
    {"width": 2.2, "flow": 10.0, "o2": 21.0,
     "start": "Figure 7.2 shows flame development stages of a 2.2-cm sample in 10-cm/s flow and 21 percent O2.",
     "end": "a steady spread rate relative to the laboratory"},
    {"width": 2.2, "flow": 5.0, "o2": 21.0,
     "start": "Figure 7.3 shows flame development stages of a 2.2-cm sample in 5-cm/s flow and 21 percent O2.",
     "end": "Steady spread time lasts for about 21 s"},
]


def steady_spread_quote(c: dict[str, Any]) -> str:
    """Exact substring of p. 95 from the condition sentence to the steady-spread words."""
    text = page_text(95)
    i = text.index(c["start"])
    j = text.index(c["end"], i) + len(c["end"])
    return text[i:j]


def sibal_points(t71: pd.DataFrame, cat: pd.DataFrame) -> list[Point]:
    a6_by_id = cat[cat["pi_table"] == "A.6"].set_index("test_id")
    mapping = match_table71_to_a6(t71, cat)
    pts: list[Point] = []
    for _, r in t71.iterrows():
        tid, o2 = r["test_id"], float(r["o2_vol_percent"])
        f0, f1, comment = float(r["flow_start_cm_s"]), float(r["flow_end_cm_s"]), r["comment"]
        a6 = a6_by_id.loc[mapping[tid]] if tid in mapping else None
        obs = "" if a6 is None else str(a6["observations_raw"])
        a6page = None if a6 is None else int(a6["source_page"])
        cond = "Table 7.1 p. 96"
        excl = ""
        if comment.startswith("Reused"):
            excl = "reused sample (Table 7.1)"
        elif r["o2_footnote_b"]:
            excl = "O2 flagged by NASA (Table 7.1 footnote b: 'O2 reading in these two tests might be inaccurate')"

        def P(flow, burn, conf, rule, quote, page):
            pts.append(Point(tid, flow, burn, o2, conf, rule, quote, page, "Table 7.1 O2", cond, excl))

        row71 = r["row_text"]
        if comment == "Quenched":
            P(f0, 1, "medium" if "Brief ignition" in obs else "high", "v1_flame_before_ramp", row71, 96)
            ext = [h for h in stated_extinction_hits(obs) if h.mode == "quote"]
            if ext:
                P(f1, 0, "high", "stated_extinction_at_flow", ext[0].quote, a6page)
            else:
                P(f1, 0, "high", "v1_quenched_end", row71, 96)
        elif comment == "Blow-off":
            P(f0, 1, "high", "v1_flame_before_ramp", row71, 96)
            h = stated_extinction_hits(obs)
            P(f1, 0, "high", "stated_extinction_at_flow", h[0].quote if h else row71, a6page if h else 96)
        elif comment == "No blowoff":
            P(f0, 1, "high", "v1_flame_before_ramp", row71, 96)
            h = no_blowoff_hits(obs)
            P(f1, 1, "high", "no_blowoff_at_max", h[0].quote if h else row71, a6page if h else 96)
        elif comment == "No ignition":
            h = no_sustained_ignition_hits(obs)
            P(f0, 0, "high", "no_sustained_ignition" if h else "v1_no_ignition", h[0].quote if h else row71, a6page if h else 96)
        elif comment.startswith("Reused"):
            h = no_sustained_ignition_hits(obs)
            if "did not ignite" in comment and f0 == f1:
                P(f0, 0, "high", "no_sustained_ignition", row71, 96)
            elif "ignited" in comment:
                P(f0, 1, "medium", "flame_present_before_ramp", row71, 96)
        elif comment == "BASS":
            for c in STEADY_SPREAD_TEXT:
                if (c["width"], c["flow"], c["o2"]) == (float(r["sample_width_cm"]), f0, o2) and f0 == f1:
                    P(f0, 1, "high", "text_reports_steady_spread__unique_condition_match", steady_spread_quote(c), 95)
        else:  # no outcome in Table 7.1: use the A.6 sentence, if any
            burn = stated_burning_hits(obs)
            hedge = hedged_burning_hits(obs)
            if burn:
                h = burn[0]
                flow = h.flows[0] if h.flows else f1
                if flow not in (f0, f1):
                    flow = f1  # Table 7.1 governs the SIBAL flows; A.6 values are noted in the audit
                P(flow, 1, "high", "stated_burning_at_flow", h.quote, a6page)
                if f0 != flow:
                    P(f0, 1, "medium", "flame_present_before_ramp", h.quote, a6page)
            elif hedge:
                for flow in _unique([f0, f1]):
                    P(flow, 1, "medium", "hedged_burning", hedge[0].quote, a6page)
            elif "in the burn" in obs:  # GMT45-T2: "... very late in the burn changed to 4"
                q = obs[obs.find("Flow velocity changed"):].strip()
                for flow in _unique([f0, f1]):
                    P(flow, 1, "medium", "flame_present_before_ramp", q, a6page)
    return pts


# --------------------------------------------------------------------------- #
# Main derivation
# --------------------------------------------------------------------------- #
def _exclusion(row: pd.Series, p: Point) -> str:
    reasons = []
    if p.exclusion_reason:
        reasons.append(p.exclusion_reason)
    if row is not None:
        if row["sample_reuse_of"]:
            reasons.append(f"reused sample (same sample number as {row['sample_reuse_of']})")
        if re.search(r"\b[Rr]eburn\b|\b[Rr]eused\b", str(row["observations_raw"])):
            reasons.append("text says reburn/reused")
        if row["flow_configuration"] == "unknown":
            reasons.append("flow configuration unknown ('?')")
        if row["material_family"] in ("candle_wax", "PMMA_sphere"):
            reasons.append(f"{row['material_family']} test (excluded family)")
    if not _o2_ok(p.o2_pct):
        reasons.append(f"O2 value used ({p.o2_pct}) missing or outside 10-30 vol%")
    if not p.flow_cm_s or p.flow_cm_s <= 0:
        reasons.append("no cm/s value")
    return "; ".join(dict.fromkeys(reasons))


def derive(cat: pd.DataFrame | None = None) -> pd.DataFrame:
    cat = pd.read_csv(CATALOG_CSV, keep_default_na=False, na_values=[""]) if cat is None else cat
    cat = cat.copy()
    for c in ("sample_reuse_of", "observations_raw", "air_display_raw", "o2_flag", "pmma_color"):
        cat[c] = cat[c].fillna("").astype(str)
    t71, t51 = parse_table_7_1(), parse_table_5_1().set_index("test_id")
    rows_by_id = cat.set_index("test_id")

    raw_pts: list[Point] = []
    for _, row in cat.iterrows():
        if row["material_family"] == "SIBAL_fabric" or row["test_id"] in AMBIGUOUS_TESTS or row["test_id"] in HARDWARE_ONLY:
            continue
        raw_pts += appendix_points(row)
    raw_pts += table_5_1_points(t51.reset_index())
    raw_pts += sibal_points(t71, cat)

    a6_map = match_table71_to_a6(t71, cat)
    records = []
    for p in raw_pts:
        a_id = a6_map.get(p.test_id, p.test_id) if p.test_id.startswith("GMT") else p.test_id
        row = rows_by_id.loc[a_id] if a_id in rows_by_id.index and not p.test_id.startswith("GMT9") \
            and not p.test_id.startswith(("GMT131", "GMT222")) else None
        rec = asdict(p)
        if p.test_id.startswith("GMT"):  # SIBAL: Table 7.1 conditions
            r71 = t71.set_index("test_id").loc[p.test_id]
            fam, th, w, d, cfg = "SIBAL_fabric", SIBAL_THICKNESS_MM, float(r71["sample_width_cm"]), None, "concurrent"
            pi_table, pi, color, sides = "7.1/A.6", "T'ien", "", None
            rec["exclusion_reason"] = "; ".join(x for x in [p.exclusion_reason] if x)
            if not _o2_ok(p.o2_pct):
                rec["exclusion_reason"] = "; ".join(filter(None, [rec["exclusion_reason"], "O2 outside 10-30 vol%"]))
        else:
            fam, th, w, d, cfg = row["material_family"], row["thickness_mm"], row["width_cm"], row["diameter_mm"], row["flow_configuration"]
            pi_table, pi, color = row["pi_table"], row["pi"], row["pmma_color"]
            sides = None
            if p.test_id in t51.index:  # Miller slabs: Table 5.1 is the PI's curated thickness / width / sides
                th, w, sides = float(t51.loc[p.test_id, "thickness_mm"]), float(t51.loc[p.test_id, "width_cm"]), int(t51.loc[p.test_id, "sides_burning"])
            rec["exclusion_reason"] = _exclusion(row, p)
        rec.update({"appendix_test_id": a_id if row is not None else "", "pi_table": pi_table, "pi": pi,
                    "material_family": fam, "thickness_mm": th, "width_cm": w, "diameter_mm": d,
                    "flow_configuration": cfg, "pmma_color": color, "sides_burning": sides})
        records.append(rec)

    df = pd.DataFrame(records)
    df["_prio"] = df["derivation_rule"].map({r: i for i, r in enumerate(RULE_PRIORITY)})
    df["_conf"] = df["label_confidence"].map({"high": 0, "medium": 1})
    df = df.sort_values(["test_id", "flow_cm_s", "burn", "_conf", "_prio"])
    df = df.drop_duplicates(subset=["test_id", "flow_cm_s", "burn", "o2_pct"], keep="first")
    # Same test, flow and O2 with both outcomes: contradictory -> keep for display, exclude from training.
    clash = df.groupby(["test_id", "flow_cm_s", "o2_pct"])["burn"].transform("nunique") > 1
    df.loc[clash, "exclusion_reason"] = df.loc[clash, "exclusion_reason"].map(
        lambda s: "; ".join(filter(None, [s, "both outcomes at the same test, flow and O2"])))
    df["include_in_training"] = df["exclusion_reason"].fillna("") == ""
    df["point_id"] = [f"{t}_{'b' if b else 'x'}{f:g}" + ("" if o is None or pd.isna(o) else f"@{o:g}")
                      for t, b, f, o in zip(df["test_id"], df["burn"], df["flow_cm_s"], df["o2_pct"])]
    assert df["point_id"].is_unique, df[df["point_id"].duplicated(keep=False)]
    df = df.sort_values(["material_family", "test_id", "flow_cm_s", "burn"]).reset_index(drop=True)
    return df[POINT_COLUMNS]


def verify_quotes(points: pd.DataFrame, cat: pd.DataFrame | None = None) -> list[str]:
    """Every evidence_quote must be an exact substring of its test's Appendix A observation text or of the
    whitespace-normalized text of its source page. Returns the list of failures (empty = all good)."""
    cat = pd.read_csv(CATALOG_CSV, keep_default_na=False) if cat is None else cat
    obs = dict(zip(cat["test_id"], cat["observations_raw"].astype(str)))
    bad = []
    for _, p in points.iterrows():
        q = str(p["evidence_quote"])
        in_obs = q in obs.get(str(p["appendix_test_id"]), "") or q in obs.get(str(p["test_id"]), "")
        in_page = normalize_ws(q) in page_text(int(p["source_page"]))
        if not (in_obs or in_page):
            bad.append(f"{p['point_id']}: quote not found: {q[:80]!r}")
    return bad


def summary(points: pd.DataFrame) -> str:
    t = points[points["include_in_training"]]
    tab = t.groupby(["material_family", "flow_configuration", "burn"]).size().unstack(fill_value=0)
    tab.columns = [f"burn={c}" for c in tab.columns]
    return tab.to_string()


def main() -> None:
    pts = derive()
    bad = verify_quotes(pts)
    if bad:
        raise SystemExit("Evidence quotes not found in the source text:\n" + "\n".join(bad))
    OUT_POINTS.parent.mkdir(parents=True, exist_ok=True)
    pts.to_csv(OUT_POINTS, index=False)
    tr = pts[pts["include_in_training"]]
    print(f"Points: {len(pts)} ({len(tr)} for training from {tr['test_id'].nunique()} tests) -> {OUT_POINTS.relative_to(ROOT)}")
    print(f"Confidence (training): {tr['label_confidence'].value_counts().to_dict()}")
    print("Training points per material family x configuration x burn:")
    print(summary(pts))
    ex = pts[~pts["include_in_training"]]
    print(f"Excluded points: {len(ex)}")
    print(ex["exclusion_reason"].str.split("; ").explode().value_counts().to_string())


if __name__ == "__main__":
    main()
