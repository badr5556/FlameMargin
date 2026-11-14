"""Every curated fact has a source, a boolean `verified` flag and matches the claims sheet."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import copilot_facts  # noqa: E402

SHEET = (ROOT / "docs" / "science" / "claims_sheet.md").read_text(encoding="utf-8")
VERIFIED_IDS = {"C2", "C2b", "C2c", "C2d", "C3", "C4", "C5", "C6", "C7", "C8", "C8b", "C10", "C11", "D3"}


@pytest.mark.parametrize("topic", list(copilot_facts.FACTS))
def test_fact_has_source_and_boolean_verified(topic):
    f = copilot_facts.FACTS[topic]
    assert f["source"].strip()
    assert isinstance(f["verified"], bool)
    assert re.fullmatch(r"[CD]\d+[a-d]?", f["claim_id"])
    assert f"| {f['claim_id']} |" in SHEET


def test_verified_flags_match_the_claims_sheet():
    flagged = {f["claim_id"] for f in copilot_facts.FACTS.values() if f["verified"]}
    assert flagged == VERIFIED_IDS
    for cid in VERIFIED_IDS:
        row = next(line for line in SHEET.splitlines() if line.startswith(f"| {cid} |"))
        assert "VERIFIED" in row or "CORRECTED" in row
        assert "checked 2026-11-14" in row


def test_verified_fact_wording_is_the_sheet_wording():
    def norm(t: str) -> str:
        return re.sub(r"[\s*_]+", " ", t.replace("–", "-")).strip().lower()

    sheet = norm(SHEET)
    for f in copilot_facts.FACTS.values():
        if f["verified"]:
            core = f["fact"].split(" (context only")[0]
            assert norm(core) in sheet, f["claim_id"]


def test_new_facts_present():
    ids = {f["claim_id"] for f in copilot_facts.FACTS.values()}
    assert {"C2b", "C2c", "C2d", "C7", "C8b", "D3"} <= ids


def test_removed_wording_is_gone():
    blob = " ".join(f["fact"] for f in copilot_facts.FACTS.values()).lower()
    for bad in ("may not be enough", "only in µg", "only in microgravity", "buoyant flow of", "no lunar-gravity combustion data"):
        assert bad not in blob
