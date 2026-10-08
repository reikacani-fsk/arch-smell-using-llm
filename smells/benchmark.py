"""Benchmark = one row per (package, smell) for all smelly packages + a sample of clean packages.

Manual validation columns `label`, `rater2_label`, `rationale` are filled by hand (Excel/LibreOffice).
`label` (1 = smell, 0 = no smell) is the validated reference used in the thesis.
"""
import random

import pandas as pd
from sklearn.metrics import cohen_kappa_score

COLUMNS = ["project", "release", "package", "smell", "tool_flag", "structural_flag",
           "tool_cause", "structural_evidence", "label", "rater2_label", "rationale"]


def build_benchmark(project, release, tool_df, structural_df, all_packages, smells,
                    clean_ratio=1.0, seed=42) -> pd.DataFrame:
    tool_df = tool_df[tool_df.smell.isin(smells) & tool_df.package.isin(all_packages)]
    smelly = sorted(set(tool_df.package))
    clean_pool = sorted(set(all_packages) - set(smelly))
    n_clean = min(len(clean_pool), round(len(smelly) * clean_ratio))
    clean = sorted(random.Random(seed).sample(clean_pool, n_clean))
    tool = {(r.package, r.smell): r.cause for r in tool_df.itertuples()}
    struct = {(r.package, r.smell): r.evidence for r in structural_df.itertuples()}
    rows = []
    for pkg in smelly + clean:
        for s in smells:
            struct_flag = None if s == "FeatureConcentration" else int((pkg, s) in struct)
            rows.append({"project": project, "release": release, "package": pkg, "smell": s,
                         "tool_flag": int((pkg, s) in tool), "structural_flag": struct_flag,
                         "tool_cause": tool.get((pkg, s), ""),
                         "structural_evidence": struct.get((pkg, s), ""),
                         "label": None, "rater2_label": None, "rationale": ""})
    return pd.DataFrame(rows, columns=COLUMNS)


def crosscheck(tool_df, structural_df, packages, smells) -> pd.DataFrame:
    """Agreement between Designite and the independent structural computation, per smell."""
    out = []
    for s in smells:
        if s == "FeatureConcentration":
            continue
        t = set(tool_df[tool_df.smell == s].package) & set(packages)
        g = set(structural_df[structural_df.smell == s].package) & set(packages)
        out.append({"smell": s, "designite": len(t), "structural": len(g), "both": len(t & g),
                    "only_designite": ", ".join(sorted(t - g)), "only_structural": ", ".join(sorted(g - t))})
    return pd.DataFrame(out)


def kappa(bench: pd.DataFrame):
    both = bench.dropna(subset=["label", "rater2_label"])
    if both.empty:
        return None, 0
    return cohen_kappa_score(both.label.astype(int), both.rater2_label.astype(int)), len(both)
