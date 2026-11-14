# Source Map — NASA/TM-20210011385

## Primary source inspected
- NASA/TM-20210011385, *Burning and Suppression of Solids–II (BASS–II) Summary Report*, October 2021.
- Uploaded PDF has **141 pages** (PDF metadata), not 144.
- The report's Summary and Section 1 state that **126 tests** were conducted (printed report p. 3; PDF page 11). The report notes some samples were burned more than once.

## Source mapping for this build

| Dataset fields | Source locator in report | Evidence status |
|---|---|---|
| `test_id`, material/sample geometry, oxygen, flow, comments, flow configuration | Section 7.1, Table 7.1, printed pp. 95–96 (approximately PDF pp. 97–98) | Current 31-row CSV says it was extracted from this table; each value has not been independently transcribed against the PDF in this run. |
| Total number of BASS-II tests | Section 1.1, printed p. 3 (PDF page 11) | Directly reported: 126 tests. |
| Sample geometries and ignition method | Section 1.2, printed pp. 4–5 (PDF pages 12–13) | Directly reported narrative; PMMA rods/slabs/sphere section and cotton-fiberglass fabric, flat samples 1 or 2 cm wide. |
| Reused/altered samples and mass-loss exclusions | Section 1.5, printed p. 10 (PDF page 18) | Directly reported: 8 of the 34 returned samples had been used multiple times and modified; this is not equivalent to the 8 reused rows in the supplied SIBAL subset. |
| Miller test matrix | Appendix A, Table A.4, printed pp. 108–109 (PDF pages 116–117) | Operational test matrix; very wide table with multi-step velocity settings and qualitative observations. Not parsed into this dataset. |
| Other PI test matrices | Appendix A, Tables A.1–A.6, printed pp. 103–113 (PDF pages 111–121) | Contains PI-level operational summaries; not fully digitized into this build. |
| Flame spread-rate figures and analyses | PI-specific sections 2.1–2.3, 4.1, 5.3–5.6, 6.1, and 7.1 | Not extracted into numeric regression target in the supplied SIBAL CSV. Values must be transcribed/digitized separately with method and uncertainty. |

## Important source distinctions
- The PDF's statement “126 tests” is a report-wide count, not evidence that the current 31-row extraction contains 126 records.
- The current CSV's `source_page` strings are extraction notes, not independently verified PDF coordinates.
- Do not use values from the FlameMargin team brief as experimental measurements. It labels its flammability-map diagram as schematic, not real data.
- Appendix tables include multiple velocity settings in some tests. A start/end velocity pair is not a full velocity profile and must not be treated as a single representative velocity without a documented rule.
- This build does not digitize any plotted points and therefore contains no figure-derived measurements.
