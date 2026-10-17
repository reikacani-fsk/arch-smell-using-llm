"""Puts the architectural smells found by Designite and by each LLM prompt variant (output/llm/<N>shot/, output/llm/history/) side by side,
for every repo that has Designite results and at least one LLM result.
Usage:   python scripts/compare.py
Output:  output/comparison/counts.csv      per repo, project and smell: number of instances found by Designite, and for each
                                           variant (0shot, 1shot, ..., history) the number found by the LLM, the difference
                                           (llm - designite) and the number of namespaces flagged by both
                                           (empty when that variant has no result for the repo)
         output/comparison/instances.csv  every smell instance found by Designite or an LLM variant, one row each
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGNITE = ROOT / "output" / "designite"
LLM = ROOT / "output" / "llm"
OUT = ROOT / "output" / "comparison"
SMELLS = ["Cyclic Dependency", "Unstable Dependency", "Ambiguous Interface", "God Component",
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
    variants = sorted(p.name for p in LLM.iterdir() if p.is_dir()) if LLM.is_dir() else []
    counts, instances = [], []
    for repo_dir in sorted(p for p in DESIGNITE.iterdir() if p.is_dir() and p.name != "logs"):
        name = repo_dir.name
        llm = {v: read(LLM / v / name / "ArchSmells.csv") for v in variants if (LLM / v / name / "ArchSmells.csv").is_file()}
        if not llm:
            print(f"{name}: no LLM results, skipped")
            continue
        designite_rows, projects = designite(name)
        results = {"designite": designite_rows, **llm}
        projects += sorted({r["Project"] for rows in llm.values() for r in rows} - set(projects))

        for tool, rows in results.items():
            instances += [{"repo": name, "tool": tool, "smell": r["Smell"], "project": r["Project"],
                           "namespace": r["Namespace"], "participating_classes": r["Participating classes"],
                           "description": r["Description"]} for r in rows]

        for project in projects:
            for smell in SMELLS:
                found = {tool: [r["Namespace"] for r in rows if r["Project"] == project and r["Smell"] == smell]
                         for tool, rows in results.items()}
                row = {"repo": name, "project": project, "smell": smell, "designite": len(found["designite"])}
                for v in variants:
                    columns = [v, f"{v}_difference", f"{v}_common_namespaces"]
                    if v in found:
                        row.update(zip(columns, [len(found[v]), len(found[v]) - len(found["designite"]),
                                                 len(set(found[v]) & set(found["designite"]))]))
                    else:
                        row.update(dict.fromkeys(columns, ""))
                counts.append(row)

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
