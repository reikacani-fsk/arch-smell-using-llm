"""Compares the commits in which the LLM says the testbed's smells emerged (scripts/explain.py) with
testbed/ground_truth.json. Each smell Designite found is matched to the ground-truth smell with the same smell type and
namespace (for Cyclic Dependency and Scattered Functionality also the same components).
Needs:   output/explanations/<owner>_<repo>/explanations.json (python scripts/explain.py <owner>/<repo>)
Usage:   python testbed/score.py
Output:  output/testbed/score.csv   one row per smell: smell, expected_commit, llm_commit, verdict, llm_explanation,
                                    ground_truth_explanation (each: how the smell emerged and why it is a problem)
         verdict: correct, too_early, too_late, first_emergence (the LLM names the earlier episode of a smell that was
         removed and came back), no_answer, not_in_ground_truth, or not_found_by_designite
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


def explanation(how, why):
    """How a smell emerged and why it is a problem, in one cell."""
    return f"How: {how}\nWhy it is a problem: {why}" if how or why else ""


def main():
    if not EXPLANATIONS.is_file():
        raise SystemExit(f"Missing {EXPLANATIONS.relative_to(ROOT).as_posix()} - "
                         f"run python scripts/explain.py {TRUTH['repo']}")
    rows, seen = [], set()
    for s in json.loads(EXPLANATIONS.read_text(encoding="utf-8"))["smells"]:
        d, answer = s["designite"], s.get("answer") or {}
        llm_commit = answer.get("emerged_in", "")
        llm_explanation = explanation(answer.get("how", ""), answer.get("why_problematic", ""))
        expected = next((e for e in TRUTH["smells"] if matches(e, d)), None)
        if expected is None:
            rows.append({"smell": f"{d['Smell']} in {d['Namespace']}", "expected_commit": "",
                         "llm_commit": llm_commit, "verdict": "not_in_ground_truth",
                         "llm_explanation": llm_explanation, "ground_truth_explanation": ""})
        else:
            seen.add(expected["id"])
            rows.append({"smell": expected["id"], "expected_commit": COMMITS[expected["emerged_in"]],
                         "llm_commit": llm_commit, "verdict": verdict(expected, llm_commit),
                         "llm_explanation": llm_explanation,
                         "ground_truth_explanation": explanation(expected["how"], expected["why"])})
    for e in TRUTH["smells"]:
        if e["id"] not in seen:
            rows.append({"smell": e["id"], "expected_commit": COMMITS[e["emerged_in"]], "llm_commit": "",
                         "verdict": "not_found_by_designite", "llm_explanation": "",
                         "ground_truth_explanation": explanation(e["how"], e["why"])})

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "score.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    width = max(len(r["smell"]) for r in rows)
    print(f"{'smell':{width}}  expected    llm         verdict")
    for r in rows:
        print(f"{r['smell']:{width}}  {r['expected_commit']:10}  {r['llm_commit'][:10]:10}  {r['verdict']}")
    correct = sum(r["verdict"] == "correct" for r in rows)
    print(f"{correct}/{len(rows)} correct -> output/testbed/score.csv")


if __name__ == "__main__":
    main()
