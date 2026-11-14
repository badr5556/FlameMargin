"""Curated background facts for the FlameMargin Copilot.

The Copilot cites these to answer "why" questions instead of improvising
physics. They are background context only, NEVER a substitute for model
predictions (src/api.py).

Fact-check status (2026-11-14): every entry mirrors ``docs/science/claims_sheet.md``
(claim IDs in ``claim_id``). ``verified: True`` means a team member opened the
primary source (abstract or PDF) on 2026-11-14 and the wording here is never
stronger than it. ``verified: False`` entries are search-extract pre-checks only.
"""

from __future__ import annotations

import re
from typing import Any

FACTS_VERSION = "2026-11-14.2"
VERIFIED_ON = "primary source abstract/PDF, checked 2026-11-14"

FACTS: dict[str, dict[str, Any]] = {
    "microgravity_flame_shape": {
        "fact": "Without gravity there is no buoyant flow, so a candle flame in still air becomes round "
        "instead of teardrop-shaped.",
        "source": "NASA SVS 31394 (NASA Studies Fire in Microgravity)",
        "url": "https://svs.gsfc.nasa.gov/31394",
        "claim_id": "C1",
        "keywords": ["spherical", "buoyan", "convection", "shape", "why", "different", "microgravity", "µg", "ليه", "الجاذبية"],
        "verified": False,
    },
    "bass2_lower_o2_in_microgravity": {
        "fact": "BASS-II flame extinctions on the ISS indicated that materials can burn at a lower oxygen concentration "
        "in microgravity than in normal gravity.",
        "source": "Olson, ICES 2019",
        "url": "https://ttu-ir.tdl.org/items/1922ad9f-ef4c-4f52-96a4-980c23debe5e",
        "claim_id": "C2",
        "keywords": ["bass", "lower o2", "lower oxygen", "1 g", "earth", "normal gravity", "why", "different", "microgravity"],
        "verified": True,
    },
    "bass2_pmma_17_vs_18": {
        "fact": "In BASS-II opposed-flow tests on PMMA rods, flame spread was sustained at 17% O2 in microgravity vs 18% "
        "in normal gravity.",
        "source": "Scientific Reports 2017, doi:10.1038/s41598-017-18398-4",
        "url": None,
        "claim_id": "C2b",
        "keywords": ["pmma", "rod", "opposed", "17%", "18%", "lower o2", "lower oxygen", "bass"],
        "verified": True,
    },
    "bass2_rod_minimum_o2": {
        "fact": "BASS-II concurrent-flow PMMA rods had a minimum flammable O2 of 13.6%; opposed-flow rods 16.3%.",
        "source": "Olson et al., ICES-2019-101; cross-checked in NASA/TM-20210011385 pp. 52, 68",
        "url": "https://ttu-ir.tdl.org/bitstreams/2024efac-4733-4352-826e-8eaaa6954038/download",
        "claim_id": "C2c",
        "keywords": ["pmma", "rod", "minimum", "limiting", "13.6", "16.3", "lowest o2", "concurrent", "opposed", "limit"],
        "verified": True,
    },
    "ug_vs_1g_pmma_limits": {
        "fact": "µg limits were 1-2% O2 lower than 1 g limits; 1 g PMMA limits are 17% downward and 15.4% upward.",
        "source": "Olson et al., ICES-2019-101",
        "url": "https://ttu-ir.tdl.org/bitstreams/2024efac-4733-4352-826e-8eaaa6954038/download",
        "claim_id": "C2d",
        "keywords": ["1 g", "earth", "normal gravity", "downward", "upward", "15.4", "lower", "limit", "pmma", "why", "different"],
        "verified": True,
    },
    "nomex_bass2_not_sustained": {
        "fact": "In BASS-II on the ISS, Nomex III samples ignited only briefly and did not sustain a flame in concurrent flow at "
        "21-22.2% O2 (tests F1, F2, F3; calibrated O2 22.2%, 21% and 21.7% at 9.5, 15 and 8 cm/s).",
        "source": "NASA/TM-20210011385, Table A.2 (p. 105) and Section 3.1.1 (p. 46)",
        "url": "https://ntrs.nasa.gov/citations/20210011385",
        "claim_id": "D3",
        "keywords": ["nomex", "aramid", "fire barrier", "nomex iii", "نومكس"],
        "verified": True,
    },
    "sibal_quenching_flow": {
        "fact": "On SIBAL cotton-fiberglass fabric in microgravity, flames were quenched at low flow speeds of 1-5 cm/s, "
        "with a higher quenching speed at lower oxygen.",
        "source": "Zhao, T'ien, Ferkul, Olson 2015, NTRS 20150008962",
        "url": "https://ntrs.nasa.gov/citations/20150008962",
        "claim_id": "C3",
        "keywords": ["sibal", "quench", "low flow", "fabric", "cotton", "flow", "fans off", "ventilation"],
        "verified": True,
    },
    "exploration_atmosphere": {
        "fact": "NASA's recommended Exploration Atmosphere was revised to 8.2 psia and 34% O2 (from 8.0 psia / 32%) to "
        "reduce hypoxia; final specifications are still being evaluated.",
        "source": "NTRS 20240003211",
        "url": "https://ntrs.nasa.gov/citations/20240003211",
        "claim_id": "C4",
        "keywords": ["exploration atmosphere", "artemis", "8.2", "34%", "atmosphere", "hypoxia"],
        "verified": True,
    },
    "burning_rate_o2_limit_8_2_psia": {
        "fact": "31.4% O2 is the calculated upper limit that would not increase burning rate at 8.2 psia, so the 34% "
        "Exploration Atmosphere is an atmosphere of increased burning rate.",
        "source": "Aerospace Medicine and Human Performance 89(9), 2018, p. 792",
        "url": None,
        "claim_id": "C5",
        "keywords": ["burning rate", "31.4", "limit", "8.2 psia", "increase", "artemis"],
        "verified": True,
    },
    "nesc_flammability_hurdle": {
        "fact": "A 2026 NASA NESC study found that material flammability is the most critical hurdle in the 8.2 psia / "
        "34-40% O2 environment, where 70% of the assessed ECLSS subsystems would require material replacements, many "
        "not yet developed.",
        "source": "NASA/TM-20260003925 (NESC), 2026",
        "url": "https://ntrs.nasa.gov/citations/20260003925",
        "claim_id": "C6",
        "keywords": ["nesc", "eclss", "replacement", "hurdle", "artemis", "exploration", "34%", "critical", "data gap"],
        "verified": True,
    },
    "limited_data_above_30pct_o2": {
        "fact": "NASA has data for many materials at 30% O2, but limited material flammability data above that level.",
        "source": "NASA/TM-20260003925 (NESC-RP-20-01610), 2026",
        "url": "https://ntrs.nasa.gov/citations/20260003925",
        "claim_id": "C13",
        "keywords": ["30%", "data gap", "above 30", "limited data", "materials data"],
        "verified": False,
    },
    "sibal_burns_at_lunar_gravity": {
        "fact": "SIBAL fabric, which extinguishes immediately after ignition in Earth gravity, burned downward in air at "
        "lunar gravity in centrifuge and parabolic-flight tests; flame spread rate as a function of gravity may peak "
        "near lunar gravity.",
        "source": "NTRS 20240015307; LPSC 2026, NTRS 20260000646",
        "url": "https://ntrs.nasa.gov/citations/20240015307",
        "claim_id": "C7",
        "keywords": ["lunar", "moon", "1 g", "partial gravity", "centrifuge", "parabolic", "sibal", "القمر"],
        "verified": True,
    },
    "no_long_duration_lunar_fire_test": {
        "fact": "No long-duration fire experiment has ever been done in actual lunar gravity; NASA's FM2 will be the first "
        "combustion experiment on another world, with launch planned for late 2026.",
        "source": "LPSC 2026, NTRS 20260000646",
        "url": None,
        "claim_id": "C10",
        "keywords": ["lunar", "moon", "fm2", "mars", "no data", "habitat", "القمر"],
        "verified": True,
    },
    "ground_test_nasa_std_6001_test1": {
        "fact": "NASA relies on NASA-STD-6001B Test 1, conducted in normal Earth gravity, to screen material flammability "
        "for flight.",
        "source": "LPSC 2026, NTRS 20260000646",
        "url": None,
        "claim_id": "C11",
        "keywords": ["nasa-std-6001", "6001", "test 1", "upward", "screening", "certif", "ground test", "pass"],
        "verified": True,
    },
    "ground_test_conservative_counter_evidence": {
        "fact": "Counter-evidence: older Mir tests found the 1 g ground test conservative for the plastics they "
        "tested, compared with still or very slow air in microgravity. How conservative it is varies by material.",
        "source": "Hirsch & Beeson, SAE 2003-01-2643; NIST r0200470",
        "url": None,
        "claim_id": "C9",
        "keywords": ["mir", "nist", "conservative", "ground test", "counter", "nasa-std-6001", "6001"],
        "verified": False,
    },
    "saffire_large_scale_fire": {
        "fact": "Saffire was the first large-scale fire intentionally set inside a spacecraft in orbit (uncrewed Cygnus), "
        "with an average forced airflow of about 20 cm/s.",
        "source": "ICES-2017-224, NTRS 20170008805",
        "url": "https://ntrs.nasa.gov/citations/20170008805",
        "claim_id": "C8",
        "keywords": ["saffire", "cygnus", "large-scale", "large scale", "first fire"],
        "verified": True,
    },
    "saffire_typical_airflow": {
        "fact": "Saffire's 20-25 cm/s forced airflow is typical of spacecraft air circulation speeds (context only, not a "
        "fans-off value).",
        "source": "Legros et al., Combustion and Flame",
        "url": None,
        "claim_id": "C8b",
        "keywords": ["air circulation", "ventilation", "typical", "airflow", "fans", "saffire", "cabin flow"],
        "verified": True,
    },
}

TOPICS = list(FACTS)


def _public(topic: str) -> dict[str, Any]:
    f = FACTS[topic]
    return {
        "topic": topic, "fact": f["fact"], "source": f["source"], "url": f.get("url"),
        "claim_id": f.get("claim_id"), "verified": f["verified"],
        "verified_by": VERIFIED_ON if f["verified"] else "pending (search-extract pre-check only)",
    }


def get_fact(topic: str) -> dict[str, Any]:
    """Exact topic key, or best keyword match. Returns {"matches": [...]} or {"error": ...}."""
    t = (topic or "").strip()
    if t in FACTS:
        return {"matches": [_public(t)], "facts_version": FACTS_VERSION}
    q = t.lower()
    scored = []
    for key, f in FACTS.items():
        score = sum(1 for kw in f["keywords"] if kw.lower() in q)
        score += sum(1 for w in re.findall(r"[a-z0-9]+", q) if len(w) > 3 and w in key)
        if score:
            scored.append((score, key))
    scored.sort(reverse=True)
    if not scored:
        return {
            "error": {"type": "unknown_topic", "message": f"No curated fact for '{topic}'.", "available_topics": TOPICS}
        }
    return {"matches": [_public(k) for _, k in scored[:3]], "facts_version": FACTS_VERSION}
