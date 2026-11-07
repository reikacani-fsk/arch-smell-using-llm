"""Compares the commits in which the LLM says the testbed's smells emerged (scripts/explain.py) with
testbed/ground_truth.json. Each smell Designite found is matched to the ground-truth smell with the same smell type and
namespace (for Cyclic Dependency and Scattered Functionality also the same components).
Needs:   output/explanations/<owner>_<repo>/explanations.json (python scripts/explain.py <owner>/<repo>)
Usage:   python testbed/score.py
Output:  output/testbed/score.csv       one row per smell: smell, expected_commit, llm_commit, verdict
         verdict: correct, too_early, too_late, first_emergence (the LLM names the earlier episode of a smell that was
         removed and came back), no_answer, not_in_ground_truth, or not_found_by_designite
         output/testbed/comparison.md   per smell the LLM's how, timeline and why next to the ground truth's, with
                                        empty rating lines to fill in by hand
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TRUTH = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
EXPLANATIONS = ROOT / "output" / "explanations" / TRUTH["repo"].replace("/", "_") / "explanations.json"
OUT = ROOT / "output" / "testbed"
COMMITS = {c["step"]: c["commit"] for c in TRUTH["commits"]}


def step(commit):
    """The step (1 = oldest commit) of a short or full commit hash, or None."""
    commit = commit.strip().lower()
    if len(commit) < 7:
        return None
    return next((n for n, c in COMMITS.items() if c.startswith(commit) or commit.startswith(c)), None)


def matches(expected, d):
    if d["Smell"] != expected["smell"]:
        return False
    components = {c.strip(" .") for c in d["Description"].split(":")[-1].split("'")}
    if d["Smell"] == "Cyclic Dependency":   # Designite reports a cycle under one of its components
        return set(expected["components"]) == components
    if d["Smell"] == "Scattered Functionality" and set(expected["components"]) != components:
        return False
    return expected["namespace"] == d["Namespace"]


def verdict(expected, llm_commit):
    llm = step(llm_commit)
    if llm is None:
        return "no_answer"
    if llm == expected["emerged_in"]:
        return "correct"
    if llm == expected.get("first_emerged_in"):
        return "first_emergence"
    return "too_early" if llm < expected["emerged_in"] else "too_late"


def label(commit):
    """`commit` with its step, e.g. "b117c1ad36 (step 20)"."""
    n = step(commit)
    return f"{commit} (step {n})" if n else f"{commit} (not a commit of the repo)"


def comparison(pairs):
    """Markdown with, per smell, the ground truth and the LLM's answer one after the other."""
    lines = [f"# How the smells of {TRUTH['repo']} emerged: LLM vs ground truth", "",
             "Rate each answer, e.g. 2 = right and complete, 1 = partly right, 0 = wrong or missing.", ""]
    for row, expected, answer in pairs:
        lines += [f"## {row['smell']}", "", f"**Verdict:** {row['verdict']}", ""]
        if expected:
            first = expected.get("first_emerged_in")
            lines += [f"**Expected commit:** {label(COMMITS[expected['emerged_in']])}"
                      + (f", first emerged in {label(COMMITS[first])}" if first else ""), ""]
        if answer:
            lines += [f"**LLM's commit:** {label(answer['emerged_in']) if answer['emerged_in'] else 'none'}", ""]
        lines += ["### How", ""]
        if expected:
            lines += [f"**Ground truth:** {expected['how']}", ""]
        if answer:
            lines += [f"**LLM:** {answer['how']}", "", "**LLM's timeline:**", ""]
            lines += [f"- {label(t['commit'])}: {t['change']}" for t in answer["timeline"]] or ["- none"]
            lines.append("")
        lines += ["**Rating (how):** ", "", "### Why it is a problem", ""]
        if expected:
            lines += [f"**Ground truth:** {expected['why']}", ""]
        if answer:
            lines += [f"**LLM:** {answer['why_problematic']}", ""]
        lines += ["**Rating (why):** ", ""]
    return "\n".join(lines)


def main():
    if not EXPLANATIONS.is_file():
        raise SystemExit(f"Missing {EXPLANATIONS.relative_to(ROOT).as_posix()} - "
                         f"run python scripts/explain.py {TRUTH['repo']}")
    rows, pairs, seen = [], [], set()
    for s in json.loads(EXPLANATIONS.read_text(encoding="utf-8"))["smells"]:
        d, answer = s["designite"], s.get("answer")
        llm_commit = (answer or {}).get("emerged_in", "")
        expected = next((e for e in TRUTH["smells"] if matches(e, d)), None)
        if expected is None:
            rows.append({"smell": f"{d['Smell']} in {d['Namespace']}", "expected_commit": "",
                         "llm_commit": llm_commit, "verdict": "not_in_ground_truth"})
        else:
            seen.add(expected["id"])
            rows.append({"smell": expected["id"], "expected_commit": COMMITS[expected["emerged_in"]],
                         "llm_commit": llm_commit, "verdict": verdict(expected, llm_commit)})
        pairs.append((rows[-1], expected, answer))
    for e in TRUTH["smells"]:
        if e["id"] not in seen:
            rows.append({"smell": e["id"], "expected_commit": COMMITS[e["emerged_in"]], "llm_commit": "",
                         "verdict": "not_found_by_designite"})
            pairs.append((rows[-1], e, None))

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "score.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    (OUT / "comparison.md").write_text(comparison(pairs) + "\n", encoding="utf-8")
    width = max(len(r["smell"]) for r in rows)
    print(f"{'smell':{width}}  expected    llm         verdict")
    for r in rows:
        print(f"{r['smell']:{width}}  {r['expected_commit']:10}  {r['llm_commit'][:10]:10}  {r['verdict']}")
    correct = sum(r["verdict"] == "correct" for r in rows)
    print(f"{correct}/{len(rows)} correct -> output/testbed/score.csv, output/testbed/comparison.md")


if __name__ == "__main__":
    main()
