# Data sources (for Layer 1: data and model)

Checked: 2026-11-13 by Omar (science lead), with AI-assisted web search.

> **Honesty note.** None of the pages below could be opened from the build environment (network and tool
> permissions blocked `psi.nasa.gov`, `spaceappschallenge.org` and `ntrs.nasa.gov`). Everything here comes
> from search-engine extracts of those pages. The "Opened?" column says so for every row.
> **Before the model is trained, someone must open the PSI pages in a browser and confirm the file list.**

## TL;DR for the team: tables or images/video?

- **BASS-II on PSI (PSI-25) is a mix, not a clean table.** Per the extract, its files are: a metadata zip,
  an engineering-requirements PowerPoint, **a sample test video (MP4)**, **on-board sensor readings**
  (O2 / CO2 from the glovebox), a **summary report** and a representative flame image.
- The **per-test conditions** (material, O2, flow, outcome) live in the **summary report**, likely as tables
  in a PDF, so Plan A (tabular model) needs a PDF-to-CSV extraction step. One third-party repo reports
  that this table has **no flame-spread-rate column**, so spread rates would need video (OpenCV plan) or the papers.
- Recommendation: **Plan A (tables) for the burn / no-burn and O2-limit target**, using the summary-report
  tables plus published limits from the papers in `docs/science/claims_sheet.md`. Treat OpenCV on the
  video as a stretch goal for spread rate only.

## Challenge page

| Item | Value | Opened? |
|---|---|---|
| Name | Flame in Freefall: AI-Powered Fire Safety Insights from Microgravity Combustion Data (some third-party sites write "SI-Powered") | No |
| Official URL (as linked by many 2026 participant repos) | https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall-ai-powered-fire-safety-insights-from-microgravity-combustion-data/ | **No: blocked.** Link seen in search results only. |
| What it asks for (per extracts of a page quoting the challenge text) | An interactive, AI-powered dashboard that summarizes, ranks and interprets microgravity combustion findings to give fire-safety insights for human exploration | No |
| Data it points to (per extracts) | NASA Physical Sciences Informatics (PSI); investigations named include BASS, Saffire, SAME, FLEX, ACME | No |
| Resource list | A third-party guide says the official resource list opens on the Space Apps site on Nov 13. **Not confirmed.** Check the "Resources" tab yourself. | No |

## Datasets

| Dataset | Official URL | Format (per extract) | Columns / units seen | Licence / attribution | Opened? |
|---|---|---|---|---|---|
| **BASS-II** (Burning and Suppression of Solids II), ISS Microgravity Science Glovebox, NASA Glenn, 2010-2022. PSI record **PSI-25**, version 4, DOI 10.60555/4qc4-de67 | https://psi.nasa.gov/physci/repo/data/investigations/PSI-25 | **Mixed**: metadata zip; engineering PPT; **raw data = sample MP4 video**; reference data = on-board sensor readings (CSA-CP, CDM); summary report + flame image | Test variables named in the summary: ambient O2 concentration, ventilation flow velocity, fuel type / thickness / geometry. Sensors: O2, CO2 (third-party repo also lists CO). One third-party repo says about 129 tests and **no flame-spread-rate column**. Units not seen. | **CC0-1.0** per the PSI-25 extract. Still cite: "NASA Physical Sciences Informatics, BASS-II (PSI-25), DOI 10.60555/4qc4-de67". | No (link only) |
| BASS-II Summary Report (NASA/TM-20210011385) | https://ntrs.nasa.gov/citations/20210011385 | PDF report | Video with data overlay and 35 mm stills recorded the burns; most tests well below 100 W heat release | NASA technical report (US government work); cite it | No (link only) |
| **BASS** (first campaign, includes SIBAL fabric). Third-party repos say PSI-26, DOI 10.60555/58h4-dy80 | https://psi.nasa.gov/physci/repo/ (record ID **not confirmed**) | Unknown; likely similar to BASS-II | Unknown | Likely CC0 like PSI-25; **not confirmed** | No |
| **SIBAL** (Solid Inflammability Boundary at Low-Speeds), cotton-fiberglass fabric tested in BASS and BASS-II | Part of the BASS / BASS-II records above; results paper NTRS 20150008962: https://ntrs.nasa.gov/citations/20150008962 | Not a separate PSI dataset as far as we can tell; numbers are in the paper | Quenching flow 1-5 cm/s (claims sheet C3) | Cite the paper | No |
| **Saffire-I / II / III** (large-scale fires on uncrewed Cygnus vehicles). Third-party repos say PSI-98 / 99 / 100 | https://psi.nasa.gov/physci/repo/ (record IDs **not confirmed**); results paper ICES-2017-224, NTRS 20170008805: https://ntrs.nasa.gov/citations/20170008805 | Unknown on PSI; paper is PDF | Sample 40.6 × 94 cm cotton-fiberglass; forced flow ~20 cm/s (claims sheet C8) | Unknown; third-party repos claim CC0, **not confirmed** | No |
| PSI repository as a whole | https://psi.nasa.gov/physci/repo/ ; also mirrored on AWS Open Data: https://registry.opendata.aws/nasa-psi/ | Mixed: reports, raw data, video, images. Archive said to be very large (TB scale), so download only the records you need | n/a | AWS registry says no restrictions on use; re3data lists CC BY 4.0. **Check each record's own licence line.** | No |

## What our repo contains today

- `combustion_sample.csv` on `main`: 3 rows, columns `Material, Oxygen, Burned`. It is a placeholder, not
  NASA data, and it has no pressure, flow or gravity column. It must not be described as "NASA data".
- `data/raw/bass2_appendix_a_tests.csv`: all 126 BASS-II tests from NASA/TM-20210011385 Appendix A (Tables A.1–A.6), turned
  into `data/processed/flame_points_v2.csv` (192 training points from 85 tests, five materials) with Table 7.1 and Table 5.1.
  This is the real training source; see `docs/data/extraction_audit.md` and `docs/model_card.md`.
- `data/raw/bass2_sibal_table7_1_extracted.csv`: the v1 extraction (31 SIBAL rows from Table 7.1), now verified 31/31 against
  the report text and against Zhao et al. 2015; kept for the v1 → v2 comparison.
- The Copilot runs on the real Prediction Engine (`src/api.py`); `src/copilot_mock_api.py` is a unit-test fixture only.

## Minimum columns the model needs (for teammate A)

To match the Copilot contract (`docs/copilot_integration.md`), each training row should have:
`test_id, campaign, material, o2_percent, pressure_psia, flow_velocity_cm_s, gravity, outcome (burn / extinguish / quench)`,
plus optional `spread_rate_mm_s`. Keep `test_id` traceable to the PSI record and report page so the Copilot
can cite real experiment IDs.

## Attribution text (paste into README / submission)

> This project uses data from NASA's Physical Sciences Informatics (PSI) system, including the BASS-II
> investigation (PSI-25, DOI 10.60555/4qc4-de67), and results published in the NASA Technical Reports Server.
> NASA does not endorse this project.
