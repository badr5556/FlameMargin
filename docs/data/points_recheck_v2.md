# 20% random re-check of the labelled points (final review)

`python -m src.data_pipeline.recheck_points` re-checks a seeded random 20% of `data/processed/flame_points_v2.csv` (43 of the points, `numpy.random.default_rng(2027)`) against the source text, independently of the derivation code: the quote is an exact substring of the test's observation cell or page text; the O2 is the test's calibrated initial/final O2, Table 7.1 O2 or Table 5.1 initial O2; the flow is a number written in the air-display cell or the quote, or a Table 7.1 / 5.1 velocity. Each label was also read against its quote by eye.

**Result: 43/43 points pass every check.**

| Point | Rule | burn | Confidence | Quote | O2 | Flow | Conditions from |
|---|---|---|---|---|---|---|---|
| F2_x15@21 | `no_sustained_ignition` | 0 | high | pass | pass | pass | Table A.2 p. 105 |
| B10_b2@21 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table A.1 p. 103 |
| B13_b3@21 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table A.1 p. 103 |
| B13_b10@21 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table A.1 p. 103 |
| B17_b5@17.5 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table A.1 p. 103 |
| B19_b10@17.3 | `flame_present_before_ramp` | 1 | medium | pass | pass | pass | Table A.1 p. 104 |
| B20_b5@17.4 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table A.1 p. 104 |
| O14_b5@16.3 | `flame_present_before_ramp` | 1 | medium | pass | pass | pass | Table A.5 p. 110 |
| O3a_b5@18 | `flame_present_before_ramp` | 1 | medium | pass | pass | pass | Table A.5 p. 111 |
| P1_b2@17.7 | `flame_present_before_ramp` | 1 | medium | pass | pass | pass | Table A.3 p. 106 |
| P12_b2@17.5 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table A.3 p. 106 |
| P17_b5@16.8 | `flame_present_before_ramp` | 1 | medium | pass | pass | pass | Table A.3 p. 106 |
| P2_b2.5@17.4 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table A.3 p. 106 |
| P2_b5@17.4 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table A.3 p. 106 |
| P24_b2@19 | `flame_present_before_ramp` | 1 | medium | pass | pass | pass | Table A.3 p. 107 |
| P4_b5@18.5 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table A.3 p. 107 |
| M1_b8@22.2 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table A.4 p. 108 |
| M10_b15@20.1 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| M14_x9@21.6 | `stated_extinction_at_flow` | 0 | high | pass | pass | pass | Table A.4 p. 108 |
| M14_b15@22.2 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| M15_b7@21 | `flame_present_before_ramp` | 1 | medium | pass | pass | pass | Table A.4 p. 108 |
| M15_b20@21 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| M16_b5@19.2 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| M17_b3@18.8 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| M17_b5@18.8 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| M18_b10@17.9 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| M2_b20@22.2 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| M20_x8@17.4 | `stated_extinction_at_flow` | 0 | high | pass | pass | pass | Table A.4 p. 109 |
| M20_b10@18 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| M5_x5@19 | `stated_extinction_at_flow` | 0 | high | pass | pass | pass | Table A.4 p. 109 |
| M5_b10@22.2 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| M5_b13@22.2 | `flame_present_before_ramp` | 1 | medium | pass | pass | pass | Table A.4 p. 109 |
| M8_b10@19.1 | `table_5_1_spread_rate_at_flow` | 1 | high | pass | pass | pass | Table 5.1 p. 57 |
| T3_x10@17.2 | `no_sustained_ignition` | 0 | high | pass | pass | pass | Table A.6 p. 113 |
| GMT100-T16_b3@17.6 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table 7.1 p. 96 |
| GMT100-T5_b10@18.8 | `hedged_burning` | 1 | medium | pass | pass | pass | Table 7.1 p. 96 |
| GMT175-T18_x2.6@17.4 | `v1_quenched_end` | 0 | high | pass | pass | pass | Table 7.1 p. 96 |
| GMT190-T19_b11@17.2 | `stated_burning_at_flow` | 1 | high | pass | pass | pass | Table 7.1 p. 96 |
| GMT190-T20_x3@17.2 | `stated_extinction_at_flow` | 0 | high | pass | pass | pass | Table 7.1 p. 96 |
| GMT216-T25_b5@20.8 | `flame_present_before_ramp` | 1 | medium | pass | pass | pass | Table 7.1 p. 96 |
| GMT216-T26_b5@20.8 | `flame_present_before_ramp` | 1 | medium | pass | pass | pass | Table 7.1 p. 96 |
| GMT96-T7_b10@21 | `text_reports_steady_spread__unique_condition_match` | 1 | high | pass | pass | pass | Table 7.1 p. 96 |
| GMT96-T8_b5@21 | `text_reports_steady_spread__unique_condition_match` | 1 | high | pass | pass | pass | Table 7.1 p. 96 |
