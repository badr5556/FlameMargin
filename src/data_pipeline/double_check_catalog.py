"""Independent 20% double-check of the Appendix A catalog against a second extractor.

The catalog was read with pdfplumber's table grid. This script re-reads the same PDF pages with
``pdftotext -layout`` (poppler) and, for a seeded random 20% of the 126 rows, checks that
  * the row's anchor line (as-run number followed by the test number) is found exactly once,
  * the calibrated initial and final O2 values are printed on that line,
  * every word of the observation, air-display and material text occurs in the row's line block.

Needs the report PDF and pdftotext (not needed at runtime):
    python src/data_pipeline/double_check_catalog.py PATH/TM-20210011385-95-125.pdf 2026 out.csv
"""
import re, subprocess, sys
import numpy as np, pandas as pd
pdf = sys.argv[1]; seed = int(sys.argv[2]); out = sys.argv[3]
cat = pd.read_csv("data/raw/bass2_appendix_a_tests.csv", dtype=str, keep_default_na=False)
rng = np.random.default_rng(seed)
idx = sorted(rng.choice(len(cat), size=int(np.ceil(0.2 * len(cat))), replace=False))
def layout(pdf_page):
    return subprocess.run(["pdftotext", "-layout", "-f", str(pdf_page - 94), "-l", str(pdf_page - 94), pdf, "-"],
                          capture_output=True, text=True).stdout
def words(s):
    return re.findall(r"[A-Za-z0-9.<>~?/–-]+", s)
rows = []
for i in idx:
    r = cat.iloc[i]
    txt = layout(int(r["pdf_page"]))
    lines = txt.split("\n")
    # the row's anchor line: contains the as-run number and the test id as separate tokens
    anchor = [k for k, ln in enumerate(lines) if re.search(rf"(^|\s){re.escape(r['as_run_number'])}\s+{re.escape(r['test_id'])}(\s|$)", ln)]
    checks = {}
    checks["anchor_line_found"] = len(anchor) == 1
    if anchor:
        k = anchor[0]
        block = "\n".join(lines[max(0, k - 3): k + 12])
        toks = block.split()
        checks["cal_o2_initial_on_row"] = r["cal_o2_initial_raw"] in lines[k].split()
        checks["cal_o2_final_on_row"] = r["cal_o2_final_raw"] in lines[k].split()
        # every word of the observation text occurs in the row block (layout wraps the cell)
        ow = [w for w in words(r["observations_raw"].replace("-", " ")) if len(w) > 1]
        bw = set(words(block.replace("-", " ")))
        missing = [w for w in ow if w not in bw]
        checks["observation_words_present"] = not missing
        aw = [w for w in words(r["air_display_raw"].replace("-", " ")) if len(w) > 0]
        checks["air_display_words_present"] = all(w in bw for w in aw)
        mw = [w for w in words(r["material_raw"].replace("-", " ")) if len(w) > 1]
        checks["material_words_present"] = all(w in bw for w in mw)
        note = "" if not missing else "missing words: " + ", ".join(missing[:6])
    else:
        note = "anchor line not unique"
    rows.append({"test_id": r["test_id"], "pi_table": r["pi_table"], "source_page": r["source_page"],
                 **{k: ("pass" if v else "FAIL") for k, v in checks.items()}, "note": note})
res = pd.DataFrame(rows)
res.to_csv(out, index=False)
print(res.to_string())
