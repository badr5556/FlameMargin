"""Curated background facts for the FlameMargin Copilot.

The Copilot cites these to answer "why" questions instead of improvising
physics. They are background context only, NEVER a substitute for model
predictions (src/api.py).

Fact-check status (2026-11-13): every entry was re-worded to match
``docs/science/claims_sheet.md`` (claim IDs in ``claim_id``). The primary
sources could not be opened from the build environment, only search-engine
extracts of them, so every entry stays ``verified: False`` until a human
opens the source and ticks the claim in the sheet. Wording is never stronger
than the extract.
"""

from __future__ import annotations

import re
from typing import Any

FACTS_VERSION = "2026-11-13.2"

FACTS: dict[str, dict[str, Any]] = {
    "microgravity_flame_shape": {
        "fact": "Without gravity there is no buoyant flow, so a candle flame in still air becomes round "
        "instead of the teardrop shape seen on Earth.",
        "source": "NASA SVS 31394 (NASA Studies Fire in Microgravity)",
        "claim_id": "C1",
        "keywords": ["spherical", "buoyan", "convection", "shape", "why", "different", "microgravity", "µg", "ليه", "الجاذبية"],
        "verified": False,
    },
    "bass2_lower_o2_in_microgravity": {
        "fact": "In BASS-II on the ISS, with a gentle ventilation flow, some materials kept burning at lower O2 levels "
        "than their limits measured in 1 g, which suggests the 1 g screening test is not always conservative.",
        "source": "Olson et al., ICES-2019-101; BASS-II Summary Report, NASA/TM-20210011385",
        "claim_id": "C2",
        "keywords": ["bass", "lower o2", "ventilation", "fans", "lower oxygen", "1 g", "earth", "conservative"],
        "verified": False,
    },
    "sibal_quenching_flow": {
        "fact": "On the ISS, flames on SIBAL cotton-fiberglass fabric went out when the air flow was lowered to about "
        "1-5 cm/s, and they went out at a higher flow when O2 was lower.",
        "source": "NTRS 20150008962 (BASS/BASS-II SIBAL fabric tests)",
        "claim_id": "C3",
        "keywords": ["sibal", "quench", "low flow", "fabric", "cotton", "flow", "fans off"],
        "verified": False,
    },
    "exploration_atmosphere": {
        "fact": "NASA's recommended Exploration Atmosphere is 8.2 psia with 34% O2 (revised from 8.0 psia / 32% O2); "
        "the final specification is still being evaluated.",
        "source": "NTRS 20240003211",
        "claim_id": "C4",
        "keywords": ["exploration atmosphere", "artemis", "8.2", "34%", "atmosphere"],
        "verified": False,
    },
    "burning_rate_o2_limit_8_2_psia": {
        "fact": "At 8.2 psia, the calculated O2 limit for no increase in burning rate is 31.4% O2, so a 34% O2 "
        "atmosphere counts as an increased-burning-rate atmosphere. NASA judged it acceptable, pending material testing.",
        "source": "Aerosp Med Hum Perform 89(9):792, 2018",
        "claim_id": "C5",
        "keywords": ["burning rate", "31.4", "limit", "8.2 psia", "increase"],
        "verified": False,
    },
    "limited_data_above_30pct_o2": {
        "fact": "NASA has flammability data for many materials at 30% O2, but limited material flammability data "
        "above that level.",
        "source": "NASA/TM-20260003925 (NESC-RP-20-01610), 2026",
        "claim_id": "C13",
        "keywords": ["30%", "data gap", "above 30", "limited data", "materials data", "34%", "exploration"],
        "verified": False,
    },
    "nonflammable_1g_burns_in_0g_or_lunar": {
        "fact": "Some materials that do not burn in Earth gravity can burn in microgravity, or in partial gravity "
        "like the Moon's.",
        "source": "Ferkul et al., LPSC 2026 abstract 1799, NTRS 20260000646",
        "claim_id": "C7",
        "keywords": ["lunar", "moon", "0 g", "1 g", "nonflammable", "pass", "ground test", "partial gravity"],
        "verified": False,
    },
    "no_lunar_gravity_data": {
        "fact": "No fire test has been run on the Moon yet. Lunar-gravity combustion data so far come only from short "
        "tests (parabolic flights, centrifuge, sounding rocket), and FlameMargin's training data contain none. "
        "NASA's FM2 experiment is planned to burn samples on the lunar surface.",
        "source": "Ferkul et al., LPSC 2026, NTRS 20260000646; FM2 record NTRS 20240015307",
        "claim_id": "C10",
        "keywords": ["lunar", "moon", "fm2", "partial gravity", "mars", "no data", "القمر"],
        "verified": False,
    },
    "ground_test_nasa_std_6001_test1": {
        "fact": "NASA screens cabin materials with an Earth-gravity test, NASA-STD-6001B Test 1 (Upward Flame "
        "Propagation): a material passes if the flame stops within about 15 cm and it drops no burning debris.",
        "source": "NASA-STD-6001B (Change 3), Test 1",
        "claim_id": "C11",
        "keywords": ["nasa-std-6001", "6001", "test 1", "upward", "screening", "certif", "ground test", "pass"],
        "verified": False,
    },
    "ground_test_conservative_counter_evidence": {
        "fact": "Counter-evidence: older Mir tests found the 1 g ground test conservative for the plastics they "
        "tested, compared with still or very slow air in microgravity. How conservative it is varies by material.",
        "source": "Hirsch & Beeson, SAE 2003-01-2643; NIST r0200470",
        "claim_id": "C9",
        "keywords": ["mir", "nist", "conservative", "ground test", "counter", "nasa-std-6001", "6001"],
        "verified": False,
    },
    "saffire_large_scale_fire": {
        "fact": "Saffire was the first time a large fire was set on purpose inside a spacecraft in orbit (an uncrewed "
        "cargo ship), with an average forced air flow of about 20 cm/s.",
        "source": "ICES-2017-224, NTRS 20170008805",
        "claim_id": "C8",
        "keywords": ["saffire", "cygnus", "large-scale", "large scale", "first fire"],
        "verified": False,
    },
}

TOPICS = list(FACTS)


def _public(topic: str) -> dict[str, Any]:
    f = FACTS[topic]
    return {
        "topic": topic, "fact": f["fact"], "source": f["source"],
        "claim_id": f.get("claim_id"), "verified": f["verified"],
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
