"""Asks an LLM to explain how and when each architectural smell found by Designite emerged (RQ2).
For every smell (except Dense Structure, which concerns the whole project, not specific classes) the LLM gets
Designite's finding, the smell definition from prompts/arch_smells.md, and the commits that changed the files of the
smell's participating classes, up to the analyzed commit, with their diffs. prompts/explain_smell.md is the system prompt.
Every commit the LLM cites is checked against the commits it was given (grounded = it cited only those).
Needs:   repos cloned by scripts/analyze.sh, Designite results in output/designite/, and ANTHROPIC_API_KEY in .env
Usage:   python scripts/explain.py owner/repo [...]              explain the smells of the given repos
         python scripts/explain.py --dry-run owner/repo [...]    only write the prompts, without calling the LLM
Output:  output/explanations/<owner>_<repo>/explanations.json   per smell: Designite's finding, the commits given,
                                                                the LLM's answer and the grounding check
         output/explanations/<owner>_<repo>/explanations.md     the same, readable, e.g. for developers to rate
         output/explanations/<owner>_<repo>/prompts/<n>.md      the prompt of each smell (with --dry-run: only these)
"""
import argparse
import csv
import json
import re
import subprocess

import anthropic

from compare import designite
from llm_analyze import EFFORT, MODEL, ROOT, projects

OUT = ROOT / "output" / "explanations"
SYSTEM = (ROOT / "prompts" / "explain_smell.md").read_text(encoding="utf-8")
DEFINITIONS = (ROOT / "prompts" / "arch_smells.md").read_text(encoding="utf-8")
SKIPPED_SMELLS = {"Dense Structure"}
MAX_DIFF_LINES = 200        # lines per file in a commit diff; longer diffs are cut off
MAX_DIFF_CHARS = 200_000    # all diffs of one smell (about 50k tokens); later commits get only their message
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["emerged_in", "emerged_date", "how", "timeline", "why_problematic"],
    "properties": {
        "emerged_in": {"type": "string", "description": "short hash of the commit the smell first appeared in, or empty"},
        "emerged_date": {"type": "string"},
        "how": {"type": "string"},
        "timeline": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["commit", "change"],
            "properties": {"commit": {"type": "string"}, "change": {"type": "string"}}}},
        "why_problematic": {"type": "string"},
    },
}


def git(repo_dir, *args):
    return subprocess.run(["git", "-c", "core.quotepath=off", "-C", str(repo_dir), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout


def definition(smell):
    m = re.search(rf"^## {re.escape(smell)}\n(.*?)(?=^#)", DEFINITIONS, re.M | re.S)
    return m.group(1).strip()


def class_files(repo_dir, project_files):
    """{simple class name: {repo-relative paths of the .cs files declaring it}}."""
    result = {}
    for files in project_files.values():
        for f in files:
            code = f.read_text(encoding="utf-8-sig", errors="replace")
            for name in re.findall(r"\b(?:class|interface|record|struct|enum)\s+(\w+)", code):
                result.setdefault(name, set()).add(f.relative_to(repo_dir).as_posix())
    return result


def history(repo_dir, commit, files):
    """[{commit, date, message, diff}] of the non-merge commits up to `commit` that changed `files`, oldest first."""
    log = git(repo_dir, "log", "--reverse", "--no-merges", "--format=%h%x09%ad%x09%s", "--date=short",
              "--abbrev=10", commit, "--", *files)
    commits, budget = [], MAX_DIFF_CHARS
    for line in log.splitlines():
        sha, date, message = line.split("\t", 2)
        diff = ""
        if budget > 0:
            parts = []
            for file_diff in re.split(r"^(?=diff --git )", git(repo_dir, "show", "--format=", "--no-color", sha,
                                                                "--", *files), flags=re.M):
                lines = file_diff.splitlines()
                parts.append("\n".join(lines[:MAX_DIFF_LINES]))
                if len(lines) > MAX_DIFF_LINES:
                    parts.append(f"... ({len(lines) - MAX_DIFF_LINES} more lines of this file cut off)")
            diff = "\n".join(p for p in parts if p)
            budget -= len(diff)
        commits.append({"commit": sha, "date": date, "message": message, "diff": diff})
    return commits


def prompt(smell, files, commits):
    parts = ["<smell>",
             f"Smell: {smell['Smell']}",
             f"Project: {smell['Project']}",
             f"Component: {smell['Namespace']}",
             f"Designite's finding: {smell['Description']}",
             f"Participating classes: {smell['Participating classes']}",
             "</smell>",
             f"<definition>\n{definition(smell['Smell'])}\n</definition>",
             "<files>\n" + "\n".join(sorted(files)) + "\n</files>",
             f'<commits count="{len(commits)}">']
    for c in commits:
        body = c["diff"] or "(diff left out to keep the input short)"
        parts.append(f'<commit hash="{c["commit"]}" date="{c["date"]}">\n{c["message"]}\n\n{body}\n</commit>')
    parts.append("</commits>")
    parts.append("Explain how and when this smell emerged.")
    return "\n".join(parts)


def explain(client, text):
    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": text}],
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason != "end_turn":
        raise RuntimeError(f"model stopped with '{message.stop_reason}'")
    return message, json.loads(next(b.text for b in message.content if b.type == "text"))


def grounding(answer, commits):
    """Commits the LLM cites that it was not given (all given commits changed the smell's files)."""
    given = {c["commit"] for c in commits}
    cited = {t["commit"] for t in answer["timeline"]} | ({answer["emerged_in"]} if answer["emerged_in"] else set())
    unknown = sorted(cited - given)
    return {"cited": len(cited), "unknown_commits": unknown, "grounded": not unknown}


def markdown(repo, results):
    lines = [f"# How the architectural smells of {repo} emerged", ""]
    for n, r in enumerate(results, 1):
        s, a = r["smell"], r.get("answer")
        lines += [f"## {n}. {s['Smell']} in {s['Namespace']} ({s['Project']})", "",
                  f"**Designite:** {s['Description']}", "",
                  f"**Classes:** {s['Participating classes']}", "",
                  f"**Commits given:** {len(r['commits'])}", ""]
        if not a:
            lines += [f"_No explanation: {r['error']}_", ""]
            continue
        lines += [f"**Emerged in:** {a['emerged_in'] or 'unknown'} {a['emerged_date']}", "",
                  f"**How:** {a['how']}", "", "**Timeline:**", ""]
        lines += [f"- `{t['commit']}`: {t['change']}" for t in a["timeline"]] or ["- none"]
        lines += ["", f"**Why it is a problem:** {a['why_problematic']}", ""]
        if not r["grounding"]["grounded"]:
            lines += [f"_Cites commits it was not given: {', '.join(r['grounding']['unknown_commits'])}_", ""]
    return "\n".join(lines)


def main(selected, dry_run):
    with open(ROOT / "data" / "subjects.csv", newline="") as f:
        subjects = {s["repo"]: s for s in csv.DictReader(f)}
    client = None if dry_run else anthropic.Anthropic()

    for repo in selected:
        print(repo)
        s, name = subjects.get(repo), repo.replace("/", "_")
        repo_dir = ROOT / "repos" / name
        if not s:
            print("    not in data/subjects.csv, skipped")
            continue
        if not repo_dir.is_dir() or not (ROOT / "output" / "designite" / name).is_dir():
            print("    not in repos/ or no Designite results - run scripts/analyze.sh first, skipped")
            continue
        smells = [r for r in designite(name)[0] if r["Smell"] not in SKIPPED_SMELLS]
        declared = class_files(repo_dir, projects(repo_dir))
        out = OUT / name
        (out / "prompts").mkdir(parents=True, exist_ok=True)

        results = []
        for n, smell in enumerate(smells, 1):
            classes = [c.strip() for c in smell["Participating classes"].split(";") if c.strip()]
            files = set().union(*(declared.get(c.split(".")[-1], set()) for c in classes))
            label = f"    {n}/{len(smells)} {smell['Smell']} in {smell['Namespace']}"
            if not files:
                print(f"{label}: no files found for its classes, skipped")
                continue
            commits = history(repo_dir, s["commit"], files)
            text = prompt(smell, files, commits)
            (out / "prompts" / f"{n}.md").write_text(text + "\n", encoding="utf-8")
            result = {"smell": smell, "files": sorted(files), "commits": commits}
            if dry_run:
                print(f"{label}: {len(files)} files, {len(commits)} commits, {len(text)} chars")
                continue
            try:
                message, answer = explain(client, text)
            except (anthropic.APIError, RuntimeError) as e:
                print(f"{label}: LLM failed: {e}")
                results.append({**result, "error": str(e)})
                continue
            result.update(answer=answer, grounding=grounding(answer, commits), usage=message.usage.model_dump())
            results.append(result)
            print(f"{label}: emerged in {answer['emerged_in'] or 'unknown'}"
                  f"{'' if result['grounding']['grounded'] else ' (cites unknown commits)'}")

        if not dry_run:
            (out / "explanations.json").write_text(json.dumps(
                {"repo": repo, "commit": s["commit"], "model": MODEL, "effort": EFFORT, "smells": results},
                indent=2), encoding="utf-8")
            (out / "explanations.md").write_text(markdown(repo, results), encoding="utf-8")
        print(f"    -> {out.relative_to(ROOT).as_posix()}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="+", help="owner/repo as in data/subjects.csv")
    parser.add_argument("--dry-run", action="store_true", help="only write the prompts, without calling the LLM")
    args = parser.parse_args()
    main(args.repos, args.dry_run)
