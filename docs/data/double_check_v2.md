# 20% random double-check of the transcribed catalog

The catalog was read with pdfplumber's table grid (`src/data_pipeline/extract_appendix_a.py`). For this check the
same PDF pages were re-read with a **different extractor**, `pdftotext -layout` (poppler), for a seeded random 20% of
the rows (26 of 126, `numpy.random.default_rng(2026)`), with `src/data_pipeline/double_check_catalog.py`:

- the row's anchor line (as-run number followed by the test number) is found exactly once on its page;
- the calibrated initial and final O2 values are printed on that line;
- every word of the observation, air-display and material text occurs in that row's line block.

In addition, all 126 rows were compared by eye with the rendered page images of PDF pages 111–121 (see
[`extraction_audit.md`](extraction_audit.md)).

**Result: 26/26 rows pass every check.**

| Test | Table | Page | Anchor | Cal. O2 initial | Cal. O2 final | Observation words | Air display | Material |
|---|---|---|---|---|---|---|---|---|
| B4 | A.1 | 104 | pass | pass | pass | pass | pass | pass |
| B17 | A.1 | 103 | pass | pass | pass | pass | pass | pass |
| B16 | A.1 | 103 | pass | pass | pass | pass | pass | pass |
| B10 | A.1 | 103 | pass | pass | pass | pass | pass | pass |
| B21 | A.1 | 104 | pass | pass | pass | pass | pass | pass |
| P4 | A.3 | 107 | pass | pass | pass | pass | pass | pass |
| P22a | A.3 | 107 | pass | pass | pass | pass | pass | pass |
| P22b | A.3 | 107 | pass | pass | pass | pass | pass | pass |
| P25 | A.3 | 107 | pass | pass | pass | pass | pass | pass |
| P18 | A.3 | 106 | pass | pass | pass | pass | pass | pass |
| M19 | A.4 | 109 | pass | pass | pass | pass | pass | pass |
| M4 | A.4 | 109 | pass | pass | pass | pass | pass | pass |
| O6 | A.5 | 111 | pass | pass | pass | pass | pass | pass |
| O8a | A.5 | 111 | pass | pass | pass | pass | pass | pass |
| O8b | A.5 | 111 | pass | pass | pass | pass | pass | pass |
| O11 | A.5 | 110 | pass | pass | pass | pass | pass | pass |
| O5b | A.5 | 111 | pass | pass | pass | pass | pass | pass |
| O13b | A.5 | 110 | pass | pass | pass | pass | pass | pass |
| O10 | A.5 | 110 | pass | pass | pass | pass | pass | pass |
| O15b | A.5 | 110 | pass | pass | pass | pass | pass | pass |
| T15 | A.6 | 112 | pass | pass | pass | pass | pass | pass |
| T13 | A.6 | 112 | pass | pass | pass | pass | pass | pass |
| T20 | A.6 | 112 | pass | pass | pass | pass | pass | pass |
| T7 | A.6 | 113 | pass | pass | pass | pass | pass | pass |
| T25 | A.6 | 113 | pass | pass | pass | pass | pass | pass |
| T28b | A.6 | 113 | pass | pass | pass | pass | pass | pass |

Rows checked: B4, B17, B16, B10, B21, P4, P22a, P22b, P25, P18, M19, M4, O6, O8a, O8b, O11, O5b, O13b, O10, O15b, T15, T13, T20, T7, T25, T28b.

The sample happened to contain no Table A.2 row; the four A.2 rows (F1–F4) are covered by the image comparison and
by spot tests in `tests/test_catalog_v2.py` (F1 observation text, F2/F3 calibrated O2).
