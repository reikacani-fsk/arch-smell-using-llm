"""Compares the LLM's answers for the testbed with testbed/ground_truth.json: the commits in which it says the smells
emerged (RQ2, scripts/explain.py) and its refactorings (RQ3, scripts/refactor.py), whichever results exist. Each smell
Designite found is matched to the ground-truth smell with the same smell type and namespace (for Cyclic Dependency and
Scattered Functionality also the same components).
Needs:   output/explanations/<owner>_<repo>/explanations.json (python scripts/explain.py <owner>/<repo>) and/or
         output/refactoring/<variant>/<owner>_<repo>/refactorings.json (python scripts/refactor.py <owner>/<repo>)
Usage:   python testbed/score.py
Output:  output/testbed/score.csv   one row per smell: smell, expected_commit, llm_commit, verdict, llm_explanation,
                                    ground_truth_explanation (each: how the smell emerged and why it is a problem)
         verdict: correct, too_early, too_late, first_emergence (the LLM names the earlier episode of a smell that was
         removed and came back), no_answer, not_in_ground_truth, or not_found_by_designite
         output/testbed/refactoring_score.csv   one row per variant and smell: expected_types, llm_types, type_match
                                    (yes if the LLM applied one of the expected refactorings), verdict (refactor.py's
                                    checks, or not_in_ground_truth / not_found_by_designite), llm_refactoring,
                                    ground_truth_refactoring
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TRUTH = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
NAME = TRUTH["repo"].replace("/", "_")
EXPLANATIONS = ROOT / "output" / "explanations" / NAME / "explanations.json"
REFACTORINGS = sorted((ROOT / "output" / "refactoring").glob(f"*/{NAME}/refactorings.json"))
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


def write(file, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def score_explanations():
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

    write("score.csv", rows)
    width = max(len(r["smell"]) for r in rows)
    print(f"{'smell':{width}}  expected    llm         verdict")
    for r in rows:
        print(f"{r['smell']:{width}}  {r['expected_commit']:10}  {r['llm_commit'][:10]:10}  {r['verdict']}")
    correct = sum(r["verdict"] == "correct" for r in rows)
    print(f"{correct}/{len(rows)} correct -> output/testbed/score.csv")



def refactoring(answer):
    """The LLM's refactoring in one cell: its summary and steps."""
    if not answer:
        return ""
    return answer["summary"] + "\nSteps:\n" + "\n".join(f"- {step}" for step in answer["steps"])


def score_refactorings():
    rows = []
    for file in REFACTORINGS:
        variant, seen = file.parent.parent.name, set()
        for s in json.loads(file.read_text(encoding="utf-8"))["smells"]:
            d, answer = s["designite"], s.get("answer") or {}
            llm_types = answer.get("refactorings", [])
            verdict_ = (s.get("checks") or {}).get("verdict") or ("no_answer" if s.get("error") else "not_reproduced")
            expected = next((e for e in TRUTH["smells"] if matches(e, d)), None)
            row = {"variant": variant, "smell": f"{d['Smell']} in {d['Namespace']}", "expected_types": "",
                   "llm_types": "; ".join(llm_types), "type_match": "", "verdict": verdict_,
                   "llm_refactoring": refactoring(answer), "ground_truth_refactoring": ""}
            if expected:
                seen.add(expected["id"])
                types = expected["refactoring"]["types"]
                row.update(smell=expected["id"], expected_types="; ".join(types),
                           type_match=("yes" if set(types) & set(llm_types) else "no") if llm_types else "",
                           ground_truth_refactoring=expected["refactoring"]["fix"])
            else:
                row["verdict"] = f"not_in_ground_truth ({verdict_})"
            rows.append(row)
        rows += [{"variant": variant, "smell": e["id"], "expected_types": "; ".join(e["refactoring"]["types"]),
                  "llm_types": "", "type_match": "", "verdict": "not_found_by_designite", "llm_refactoring": "",
                  "ground_truth_refactoring": e["refactoring"]["fix"]}
                 for e in TRUTH["smells"] if e["id"] not in seen]

    write("refactoring_score.csv", rows)
    width = max(len(r["smell"]) for r in rows)
    print(f"{'variant':11}  {'smell':{width}}  type match  verdict")
    for r in rows:
        print(f"{r['variant']:11}  {r['smell']:{width}}  {r['type_match']:10}  {r['verdict']}")
    for variant in dict.fromkeys(r["variant"] for r in rows):
        own = [r for r in rows if r["variant"] == variant]
        print(f"{variant}: {sum(r['verdict'] == 'fixed' for r in own)}/{len(own)} fixed, "
              f"{sum(r['type_match'] == 'yes' for r in own)}/{len(own)} expected refactoring")
    print("-> output/testbed/refactoring_score.csv")


def main():
    if not EXPLANATIONS.is_file() and not REFACTORINGS:
        raise SystemExit(f"No results for {TRUTH['repo']} - run python scripts/explain.py {TRUTH['repo']} "
                         f"and/or python scripts/refactor.py {TRUTH['repo']}")
    if EXPLANATIONS.is_file():
        score_explanations()
    if REFACTORINGS:
        score_refactorings()


if __name__ == "__main__":
    main()
