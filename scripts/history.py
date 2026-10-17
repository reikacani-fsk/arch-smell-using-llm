"""Summarizes the git history of a repo up to the analyzed commit, for llm_analyze.py --history.
Only the .cs files the LLM sees are counted (the analyzed projects at the analyzed commit); merge commits are skipped.
Changes are grouped by namespace, the component Designite reports smells for:
  - churn: in how many commits each namespace and file changed
  - co-change: how often two namespaces changed in the same commit (commits with more than MAX_FILES files,
    e.g. the initial import, are left out here, as they say nothing about which parts depend on each other)
"""
import re
import subprocess
from collections import Counter
from itertools import combinations

MAX_FILES = 30   # commits changing more analyzed files are ignored for co-change
TOP = 20         # rows per list


def namespace(path):
    code = path.read_text(encoding="utf-8-sig", errors="replace")
    m = re.search(r"^\s*namespace\s+([\w.]+)", code, re.M)
    return m.group(1) if m else "(global)"


def commits(repo_dir, commit):
    """[(date, {changed paths})] of the non-merge commits up to `commit`, oldest first."""
    out = subprocess.run(
        ["git", "-c", "core.quotepath=off", "-C", str(repo_dir), "log", "--reverse", "--no-merges", "--no-renames",
         "--name-only", "--format=@@%ad", "--date=short", commit],
        capture_output=True, text=True, encoding="utf-8", check=True).stdout
    result = []
    for block in out.split("@@")[1:]:
        date, *paths = block.strip().splitlines()
        result.append((date, {p for p in paths if p}))
    return result


def summary(repo_dir, commit, project_files):
    """(summary text for the prompt, number of commits that changed an analyzed file)."""
    component = {}   # repo-relative path -> "project/namespace"
    for project, files in project_files.items():
        for f in files:
            component[f.relative_to(repo_dir).as_posix()] = f"{project}/{namespace(f)}"

    history = [(date, paths & component.keys()) for date, paths in commits(repo_dir, commit)]
    history = [(date, paths) for date, paths in history if paths]
    if not history:
        return "", 0

    file_churn, ns_churn, ns_pairs = Counter(), Counter(), Counter()
    for _, paths in history:
        file_churn.update(paths)
        changed = sorted({component[p] for p in paths})
        ns_churn.update(changed)
        if len(paths) <= MAX_FILES:
            ns_pairs.update(combinations(changed, 2))

    n = len(history)
    lines = [f'<history commits="{n}" first="{history[0][0]}" last="{history[-1][0]}">',
             "Git history of the .cs files above, up to the analyzed version (merge commits excluded). "
             "Components are given as project/namespace.",
             "",
             "Commits per component (how often it changed):"]
    lines += [f"- {c}: {k} of {n} commits" for c, k in ns_churn.most_common(TOP)]
    lines += ["", f"Components changed in the same commit (at least 2 commits; commits with more than {MAX_FILES} files ignored):"]
    pairs = [(a, b, k) for (a, b), k in ns_pairs.most_common(TOP) if k >= 2]
    lines += [f"- {a} + {b}: {k} commits (of {ns_churn[a]} and {ns_churn[b]})" for a, b, k in pairs] or ["- none"]
    lines += ["", "Most changed files:"]
    lines += [f"- {p} ({component[p]}): {k} commits" for p, k in file_churn.most_common(TOP)]
    lines.append("</history>")
    return "\n".join(lines), n
