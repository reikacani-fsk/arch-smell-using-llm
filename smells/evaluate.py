"""RQ1 metrics: precision / recall / F1 of LLM predictions against a reference column of the benchmark.

reference = "label"          validated manual labels (the thesis result)
reference = "tool_flag"      raw Designite output
reference = "structural_flag" independent graph computation (pilot only)
Predictions over repeats are combined by majority vote.
"""
import sqlite3

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support


def load_predictions(db_path, run_id=None) -> pd.DataFrame:
    con = sqlite3.connect(db_path)
    q = "SELECT run_id, package, config, model, repeat, smell, present FROM predictions"
    df = pd.read_sql_query(q + (" WHERE run_id = ?" if run_id else ""), con,
                           params=(run_id,) if run_id else None)
    return df


def majority(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["run_id", "model", "config", "package", "smell"]).present
    return g.mean().ge(0.5).astype(int).rename("pred").reset_index()


def evaluate(bench: pd.DataFrame, preds: pd.DataFrame, reference="label") -> pd.DataFrame:
    ref = bench.dropna(subset=[reference])[["package", "smell", reference]]
    if ref.empty:
        raise ValueError(f"Reference column '{reference}' is empty. Fill it in benchmark.csv or use "
                         f"--reference tool_flag / structural_flag.")
    m = majority(preds).merge(ref, on=["package", "smell"], how="inner")
    rows = []
    for keys, grp in m.groupby(["run_id", "model", "config", "smell"]):
        y, p = grp[reference].astype(int), grp.pred
        pr, rc, f1, _ = precision_recall_fscore_support(y, p, average="binary", zero_division=0)
        rows.append(dict(zip(["run_id", "model", "config", "smell"], keys), n=len(grp), positives=int(y.sum()),
                         predicted=int(p.sum()), precision=round(pr, 3), recall=round(rc, 3), f1=round(f1, 3)))
    return pd.DataFrame(rows)
