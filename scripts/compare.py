"""Puts the architectural smells found by Designite and by the LLM side by side, for every repo that has both results.
Usage:   python scripts/compare.py
Output:  output/comparison/counts.csv      per repo, project and smell: number of instances found by Designite and
                                           by the LLM, difference (llm - designite), and the number of namespaces
                                           flagged for that smell by both
         output/comparison/instances.csv  every smell instance found by either tool, one row each
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGNITE = ROOT / "output" / "designite"
LLM = ROOT / "output" / "llm"
OUT = ROOT / "output" / "comparison"
SMELLS = ["Cyclic Dependency", "Unstable Dependency", "God Component",
          "Feature Concentration", "Scattered Functionality", "Dense Structure"]


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def designite(name):
    """Designite rows (only the smells above) and the analyzed projects, which have a file even without smells."""
    rows, projects = [], []
    for f in sorted((DESIGNITE / name).glob("Designite_*_ArchSmells.csv")):
        projects.append(f.name[len("Designite_"):-len("_ArchSmells.csv")])
        for r in read(f):
            if r["Smell"] in SMELLS:
                # Designite writes commas as "'": its list separator "' " becomes "; " as in the LLM results
                rows.append({**r, "Participating classes": r["Participating classes"].replace("' ", "; ")})
    return rows, projects


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    counts, instances = [], []
    for repo_dir in sorted(p for p in DESIGNITE.iterdir() if p.is_dir() and p.name != "logs"):
        name = repo_dir.name
        if not (LLM / name / "ArchSmells.csv").is_file():
            print(f"{name}: no LLM results, skipped")
            continue
        designite_rows, projects = designite(name)
        results = {"designite": designite_rows, "llm": read(LLM / name / "ArchSmells.csv")}
        projects += sorted({r["Project"] for r in results["llm"]} - set(projects))

        for tool, rows in results.items():
            instances += [{"repo": name, "tool": tool, "smell": r["Smell"], "project": r["Project"],
                           "namespace": r["Namespace"], "participating_classes": r["Participating classes"],
                           "description": r["Description"]} for r in rows]

        for project in projects:
            n = {tool: Counter(r["Smell"] for r in rows if r["Project"] == project) for tool, rows in results.items()}
            for smell in SMELLS:
                namespaces = [{r["Namespace"] for r in rows if r["Project"] == project and r["Smell"] == smell}
                              for rows in results.values()]
                counts.append({"repo": name, "project": project, "smell": smell,
                               "designite": n["designite"][smell], "llm": n["llm"][smell],
                               "difference": n["llm"][smell] - n["designite"][smell],
                               "common_namespaces": len(namespaces[0] & namespaces[1])})

    instances.sort(key=lambda r: (r["repo"], r["project"], r["smell"], r["namespace"], r["tool"]))
    for file, rows in (("counts.csv", counts), ("instances.csv", instances)):
        if rows:
            with open(OUT / file, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
    print(f"{len(counts)} counts, {len(instances)} instances -> output/comparison/")


if __name__ == "__main__":
    main()
