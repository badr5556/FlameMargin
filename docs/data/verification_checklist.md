# Verification checklist: 31 extracted rows vs. NASA/TM-20210011385 Table 7.1

> **Status 2026-11-14: DONE.** All 31 rows were compared programmatically with the Table 7.1 text of NASA/TM-20210011385 (p. 96):
> width, flow start/end, O2 and comment match for 31/31 rows (`tests/test_catalog_v2.py::test_table_7_1_v1_rows_verified_31_of_31`).
> They also match the appendix table of Zhao, T'ien, Ferkul, Olson 2015 (NTRS 20150008962) for 31/31 rows
> (`src/data_pipeline/crosscheck_zhao2015.py`). The manual checklist below is kept as the original plan.

*Original plan (superseded by the programmatic check above; claim D1 is now VERIFIED in `docs/science/claims_sheet.md`):*

## How to check (about 20 minutes for two people)
1. Open NASA/TM-20210011385 (BASS-II Summary Report), Section 7.1, Table 7.1, printed p. 96 (PDF p. 104).
2. Person A reads each row aloud from the PDF; person B compares it with the row here: test ID, sample width, O2 %, start and end flow, and the comment.
3. If everything matches, put ✅ and both initials in *checked by*. If anything differs, put ❌, write the PDF value next to it, and open an issue. **Do not edit `data/raw/` by hand**: a corrected extraction must be committed as a new raw file with a note.
4. When all 31 rows are ✅, change D1 in `docs/science/claims_sheet.md` to VERIFIED and update the model card.

Also worth checking while the table is open: whether the four 21% O2 `BASS` rows (GMT96-T7, GMT96-T8, GMT131-T10, GMT222-T11) report an outcome anywhere in Section 7.1. If they do, adding them would give the model labelled data at the ISS O2 level (v1: the highest labelled O2 was 18.7%; v2 found the answer on p. 95: GMT96-T7 and GMT96-T8 reached steady spread).

Label column: the extraction's `conservative_event_label`, with the table comment in brackets. Rows marked † are used for training (via `src/data_pipeline/derive_points.py`); the others are display-only.

| # | test_id | width (cm) | O2 (%) | flow start→end (cm/s) | label | ✅ matches Table 7.1? | checked by |
|---|---|---|---|---|---|---|---|
| 1 | GMT45-T1 | 2.2 | 18.5 | 10 → 10 | not_reported | ☐ | |
| 2 | GMT45-T2 | 2.2 | 18.5 | 10 → 5 | not_reported | ☐ | |
| 3 | GMT45-T4 † | 2.2 | 18.7 | 10 → 2.2 | quenched (Quenched) | ☐ | |
| 4 | GMT45-T15 † | 2.2 | 18.7 | 10 → 29 | not_reported (No blowoff) | ☐ | |
| 5 | GMT100-T5 | 2.2 | 18.8 | 10 → 2.4 | not_reported | ☐ | |
| 6 | GMT100-T6 | 2.2 | 18.8 | 4.5 → 2.6 | not_reported | ☐ | |
| 7 | GMT100-T13 † | 2.2 | 17.5 | 4 → 2.2 | quenched (Quenched) | ☐ | |
| 8 | GMT100-T16 | 2.2 | 17.6 | 4 → 3 | not_reported | ☐ | |
| 9 | GMT175-T9 † | 2.2 | 16.4 | 10 → 10 | no_ignition (No ignition) | ☐ | |
| 10 | GMT175-T10 † | 2.2 | 16.4 | 5 → 5 | no_ignition (No ignition) | ☐ | |
| 11 | GMT175-T18 † | 2.2 | 17.4 | 5 → 2.6 | quenched (Quenched) | ☐ | |
| 12 | GMT178-T11 | 2.2 | 17.1 | 4 → 4 | not_reported | ☐ | |
| 13 | GMT178-T12 † | 2.2 | 16.8 | 5 → 5 | no_ignition (No ignition) | ☐ | |
| 14 | GMT178-T14 † | 2.2 | 16.9 | 4 → 2.8 | quenched (Quenched) | ☐ | |
| 15 | GMT178-T17 † | 2.2 | 16.9 | 6 → 53 | not_reported (No blowoff) | ☐ | |
| 16 | GMT190-T19 | 1.2 | 17.2 | 11 → 11 | not_reported | ☐ | |
| 17 | GMT190-T20 † | 1.2 | 17.2 | 11 → 3 | quenched (Quenched) | ☐ | |
| 18 | GMT190-T21 † | 1.2 | 17.2 | 11 → 47 | blowoff (Blow-off) | ☐ | |
| 19 | GMT190-T22 † | 1.2 | 17.1 | 10.5 → 5 | quenched (Quenched) | ☐ | |
| 20 | GMT190-T23 | 2.2 | 17.2 | 10 → 10 | no_ignition_reused (Reused, did not ignite) | ☐ | |
| 21 | GMT190-T24 | 2.2 | 18.2 | 10 → 10 | one_sided_flame_reused (Reused, one-sided flame) | ☐ | |
| 22 | GMT216-T25 | 2.2 | 20.8 | 5 → 2.5 | ignited_reused (Reused, ignited) | ☐ | |
| 23 | GMT216-T26 | 2.2 | 20.8 | 5 → 2.5 | ignited_reused (Reused, ignited) | ☐ | |
| 24 | GMT216-T27 | 1.2 | 20.7 | 5 → 2 | ignited_reused (Reused, ignited) | ☐ | |
| 25 | GMT216-T28a | 1.2 | 20.7 | 5 → 5 | no_ignition_reused (Reused, did not ignite) | ☐ | |
| 26 | GMT216-T28b | 1.2 | 20.7 | 5 → 5 | no_ignition_reused (Reused, did not ignite) | ☐ | |
| 27 | GMT216-T29 | 1.2 | 20.7 | 5 → 2 | ignited_reused (Reused, ignited) | ☐ | |
| 28 | GMT96-T8 | 2.2 | 21 | 5 → 5 | not_reported (BASS) | ☐ | |
| 29 | GMT96-T7 | 2.2 | 21 | 10 → 10 | not_reported (BASS) | ☐ | |
| 30 | GMT131-T10 | 1.2 | 21 | 11 → 11 | not_reported (BASS) | ☐ | |
| 31 | GMT222-T11 | 1.2 | 21 | 19 → 19 | not_reported (BASS) | ☐ | |

† = 12 tests that produce the 21 training points.
