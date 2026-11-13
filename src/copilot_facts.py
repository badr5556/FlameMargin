"""Curated background facts for the FlameMargin Copilot.

The Copilot cites these to answer "why" questions instead of improvising
physics. They are background context only, NEVER a substitute for model
predictions (src/api.py).

Every entry has ``verified: False`` until the team's science lead checks it
against the source. Source strings are kept verbatim from the team brief.
"""

from __future__ import annotations

import re
from typing import Any

FACTS_VERSION = "2026-11-13.1"

FACTS: dict[str, dict[str, Any]] = {
    "microgravity_flame_shape": {
        "fact": "Without gravity there is no buoyant convection, so flames in microgravity become spherical "
        "instead of the teardrop shape seen on Earth.",
        "source": "NASA SVS 31394",
        "keywords": ["spherical", "buoyan", "convection", "shape", "why", "different", "microgravity", "µg", "ليه", "الجاذبية"],
        "verified": False,
    },
    "bass2_lower_o2_in_microgravity": {
        "fact": "BASS-II found that materials can burn at lower O2 concentrations in microgravity than in 1 g, and "
        "that ventilation shutdown may not be enough to extinguish a fire at high O2 / low pressure.",
        "source": "Olson et al., ICES 2019",
        "keywords": ["bass", "lower o2", "ventilation", "fans", "shutdown", "lower oxygen", "1 g", "earth"],
        "verified": False,
    },
    "sibal_quenching_flow": {
        "fact": "In SIBAL, cotton-fiberglass fabric quenched at flow speeds of 1–5 cm/s in microgravity, while the "
        "minimum buoyant flow in 1 g is about 20 cm/s, so this low-flow quenching branch exists only in microgravity.",
        "source": "NTRS 20150008962; Ferkul et al., USCI 2013",
        "keywords": ["sibal", "quench", "low flow", "fabric", "cotton", "flow", "fans off"],
        "verified": False,
    },
    "exploration_atmosphere": {
        "fact": "The Exploration Atmosphere is 8.2 psia with 34% O2.",
        "source": "NTRS 20240003211",
        "keywords": ["exploration atmosphere", "artemis", "8.2", "34%", "atmosphere"],
        "verified": False,
    },
    "burning_rate_o2_limit_8_2_psia": {
        "fact": "The calculated O2 limit for no increase in burning rate at 8.2 psia is 31.4% O2.",
        "source": "Aerosp Med Hum Perform 89(9)",
        "keywords": ["burning rate", "31.4", "limit", "8.2 psia", "increase"],
        "verified": False,
    },
    "nonflammable_1g_burns_in_0g_or_lunar": {
        "fact": "Some materials that do not burn in 1 g do burn in 0 g with low-speed flow, or in lunar gravity.",
        "source": "Ferkul et al., LPSC 2026, NTRS 20260000646",
        "keywords": ["lunar", "moon", "0 g", "1 g", "nonflammable", "pass", "ground test", "partial gravity"],
        "verified": False,
    },
    "no_lunar_gravity_data": {
        "fact": "No lunar-gravity combustion data exists yet; NASA's FM2 experiment is planned to address this.",
        "source": "Copernical, Apr 2026",
        "keywords": ["lunar", "moon", "fm2", "partial gravity", "mars", "no data", "القمر"],
        "verified": False,
    },
    "ground_test_conservative_counter_evidence": {
        "fact": "Counter-evidence: older Mir/NIST comparisons found the 1 g ground test to be conservative. "
        "Whether ground tests are conservative depends on the material and conditions.",
        "source": "SAE 2003-01-2643",
        "keywords": ["mir", "nist", "conservative", "ground test", "counter", "nasa-std-6001", "6001"],
        "verified": False,
    },
}

TOPICS = list(FACTS)


def _public(topic: str) -> dict[str, Any]:
    f = FACTS[topic]
    return {"topic": topic, "fact": f["fact"], "source": f["source"], "verified": f["verified"]}


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
