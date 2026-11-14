# Data Dictionary

## Scope and interpretation
This dictionary describes the current 31-row SIBAL fabric extraction, not all 126 BASS-II tests. Original extracted columns are preserved; pipeline-added fields are explicitly identified. No scientific units were converted.

| Column | Meaning | Type | Unit | Role | Missing-value meaning | Source location |
|---|---|---|---|---|---|---|
| record_id | Sequential row identifier created by this pipeline | integer | none | metadata | never missing | Generated; not a NASA test identifier. |
| test_id | NASA test identifier as supplied in extraction | string | none | metadata/group key | never missing | Section 7.1, Table 7.1; printed pp. 95–96 (extraction citation; confirm against report table). |
| campaign | Campaign label in extraction | string | none | metadata | never missing | Extraction; report describes BASS and BASS-II operations. |
| material | Sample material description | string | none | feature | never missing | Section 7.1, Table 7.1; printed pp. 95–96. |
| sample_width_cm | Sample width | float | cm | feature | not reported if null | Section 7.1, Table 7.1. |
| flow_start_cm_s | Starting forced-flow velocity in extraction | float | cm/s | feature/condition | not reported if null | Section 7.1, Table 7.1. |
| flow_end_cm_s | Ending forced-flow velocity in extraction | float | cm/s | feature/condition | not reported if null | Section 7.1, Table 7.1. |
| o2_vol_percent | Initial oxygen volume percentage in extraction | float | vol% | feature/condition | not reported if null; some source footnotes flag uncertainty | Section 7.1, Table 7.1. |
| reported_comment | Qualitative observation copied from extraction | string | none | qualitative outcome | blank means no comment was extracted; not a negative result | Section 7.1, Table 7.1. |
| conservative_event_label | Conservative event label supplied by prior extraction | category | none | candidate target/qualitative label | not_reported means source extraction did not provide a definitive event | Derived extraction; not a canonical NASA label. |
| reused_sample | Whether sample was reused according to extraction | boolean | none | quality/control metadata | False/True only in current extract | Section 7.1 notes; report discusses reused/altered samples generally in Section 1.5, printed p. 10. |
| sample_length_cm | Sample length | float | cm | feature | not reported if null | Section 7.1, Table 7.1. |
| sample_thickness_mm_approx | Approximate sample thickness | float | mm | feature | approximate by column name; null if not reported | Section 7.1, Table 7.1. |
| pressure_atm | Pressure | float | atm | condition | not reported if null | Extraction; report general test conditions in Section 1.2. |
| gravity_environment | Gravity environment text | string | none | condition | not reported if null | BASS-II experiment conducted in ISS microgravity; Section 1.2. |
| flow_configuration | Concurrent/opposed configuration as extracted | category | none | feature/condition | not reported if null | Section 7.1, Table 7.1. |
| source | Citation text supplied by extraction | string | none | source reference | never missing in supplied rows | Extraction source pointer; verify precise row against Table 7.1. |
| source_page | Printed/PDF page hint supplied by extraction | string | page locator | source reference | not reported if null | Extraction source pointer; printed pp. 95–96 and approximate PDF pp. 97–98. |
| notes | Extraction caveats and interpretation notes | string | none | quality metadata | blank means no note supplied | Prior extraction notes; not a NASA measurement. |
| source_verification_status | Pipeline verification state | string | none | provenance metadata | never missing | Pipeline-generated; all rows are secondary extraction, not independently transcribed. |
| measurement_type | Representation type for current row | string | none | metadata | never missing | Pipeline-generated. |
| airflow_velocity_cm_s | Single scalar airflow velocity; intentionally null because start/end pair is not one scalar | float | cm/s | potential feature | intentionally null until a scientifically justified selection/long format is supplied | No single value asserted. |
| ignition_outcome | Canonical ignition outcome; intentionally unassigned | string | none | potential target | intentionally null; extraction labels do not fully establish ignition for all rows | Requires source-level review of Section 7.1. |
| sustained_combustion | Whether combustion was sustained; intentionally unassigned | boolean | none | potential target | intentionally null; do not infer from 'no blowoff' or missing comment | Requires source-level review of Section 7.1. |
| flame_spread_rate_mm_s | Numerical flame spread rate; intentionally null in this SIBAL subset | float | mm/s | regression target | no numerical rate in supplied extraction | No numerical spread-rate values supplied in current SIBAL CSV. |
| flow_start_cm_s_original | Exact copied start-flow value retained before transformation | float | cm/s | original-value preservation | same as source nullability | Copied from flow_start_cm_s without conversion. |
| flow_end_cm_s_original | Exact copied end-flow value retained before transformation | float | cm/s | original-value preservation | same as source nullability | Copied from flow_end_cm_s without conversion. |
