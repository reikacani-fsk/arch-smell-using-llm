"""Asks an LLM to explain how and when each architectural smell found by Designite emerged (RQ2).
One LLM call per project: it gets all Designite smells of the project (with their participating classes and the files
declaring them), the smell definitions from prompts/arch_smells.md, and once the commits that changed those files, up to
the analyzed commit, each with its diff and changed files. prompts/explain_smell.md is the system prompt.
Designite reports Dense Structure for "<All projects included>", so it gets its own call.
Every commit the LLM cites for a smell is checked: grounded = it cited only commits that changed that smell's files.
Needs:   repos cloned by scripts/analyze.sh, Designite results in output/designite/, and ANTHROPIC_API_KEY in .env
Usage:   python scripts/explain.py owner/repo [...]              explain the smells of the given repos
         python scripts/explain.py --dry-run owner/repo [...]    only write the prompts, without calling the LLM
Output:  output/explanations/<owner>_<repo>/explanations.json   per smell: Designite's finding, its files and commits,
                                                                the LLM's answer and the grounding check; per call: usage
         output/explanations/<owner>_<repo>/explanations.md     the same, readable, e.g. for developers to rate
         output/explanations/<owner>_<repo>/prompts/<project>.md  the prompt of each call (with --dry-run: only these)
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
MAX_DIFF_LINES = 200        # lines per file in a commit diff; longer diffs are cut off
MAX_DIFF_CHARS = 400_000    # all diffs of one call (about 100k tokens); later diffs are left out
ALL_PROJECTS = "<All projects included>"   # Designite's project for Dense Structure
EXPLANATION = {
    "type": "object",
    "additionalProperties": False,
    "required": ["smell_id", "emerged_in", "emerged_date", "how", "timeline", "why_problematic"],
    "properties": {
        "smell_id": {"type": "integer"},
        "emerged_in": {"type": "string", "description": "short hash of the commit the smell first appeared in, or empty"},
        "emerged_date": {"type": "string"},
        "how": {"type": "string"},
        "timeline": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["commit", "change"],
            "properties": {"commit": {"type": "string"}, "change": {"type": "string"}}}},
        "why_problematic": {"type": "string"},
    },
}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["explanations"],
          "properties": {"explanations": {"type": "array", "items": EXPLANATION}}}


def git(repo_dir, *args):
    return subprocess.run(["git", "-c", "core.quotepath=off", "-C", str(repo_dir), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout


def definition(smell):
    m = re.search(rf"^## {re.escape(smell)}\n(.*?)(?=^#)", DEFINITIONS, re.M | re.S)
    return m.group(1).strip()


def class_files(repo_dir, project_files):
    """{project: {simple class name: {repo-relative paths of the .cs files declaring it}}}, plus ALL_PROJECTS for
    smells Designite reports for the whole solution."""
    result = {ALL_PROJECTS: {}}
    for project, files in project_files.items():
        for f in files:
            code = f.read_text(encoding="utf-8-sig", errors="replace")
            for name in re.findall(r"\b(?:class|interface|record|struct|enum)\s+(\w+)", code):
                for key in (project, ALL_PROJECTS):
                    result.setdefault(key, {}).setdefault(name, set()).add(f.relative_to(repo_dir).as_posix())
    return result


def history(repo_dir, commit, files):
    """[{commit, date, message, files, diff}] of the non-merge commits up to `commit` that changed `files`, oldest
    first; `files` of a commit are the given files it changed, `diff` its diff of them (empty once the budget is used)."""
    log = git(repo_dir, "log", "--reverse", "--no-merges", "--name-only", "--format=@@%h%x09%ad%x09%s",
              "--date=short", "--abbrev=10", commit, "--", *sorted(files))
    commits, budget = [], MAX_DIFF_CHARS
    for block in log.split("@@")[1:]:
        header, *changed = block.strip().splitlines()
        sha, date, message = header.split("\t", 2)
        diff = ""
        if budget > 0:
            parts, left_out = [], 0
            for file_diff in re.split(r"^(?=diff --git )", git(repo_dir, "show", "--format=", "--no-color", sha,
                                                                "--", *sorted(files)), flags=re.M):
                if not file_diff.strip():
                    continue
                if budget <= 0:
                    left_out += 1
                    continue
                lines = file_diff.splitlines()
                part = "\n".join(lines[:MAX_DIFF_LINES])
                if len(lines) > MAX_DIFF_LINES:
                    part += f"\n... ({len(lines) - MAX_DIFF_LINES} more lines of this file cut off)"
                parts.append(part)
                budget -= len(part)
            if left_out:
                parts.append(f"... (diffs of {left_out} more files left out to keep the input short)")
            diff = "\n".join(parts)
        commits.append({"commit": sha, "date": date, "message": message,
                        "files": sorted(set(changed) & files), "diff": diff})
    return commits


def prompt(project, smells, commits):
    parts = [f'<smells project="{project}">']
    for i, s in enumerate(smells, 1):
        d = s["designite"]
        parts += [f'<smell id="{i}">',
                  f"Smell: {d['Smell']}",
                  f"Component: {d['Namespace']}",
                  f"Designite's finding: {d['Description']}",
                  f"Participating classes: {d['Participating classes']}",
                  "Files: " + ", ".join(s["files"]),
                  "</smell>"]
    parts.append("</smells>")
    parts.append("<definitions>")
    for name in dict.fromkeys(s["designite"]["Smell"] for s in smells):
        parts.append(f"## {name}\n{definition(name)}")
    parts.append("</definitions>")
    parts.append(f'<commits count="{len(commits)}">')
    for c in commits:
        body = c["diff"] or "(diff left out to keep the input short)"
        parts.append(f'<commit hash="{c["commit"]}" date="{c["date"]}">\n{c["message"]}\n'
                     f'Changed files: {", ".join(c["files"])}\n\n{body}\n</commit>')
    parts.append("</commits>")
    parts.append("Explain for each smell above how and when it emerged.")
    return "\n".join(parts)


def explain(client, text):
    with client.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=SYSTEM,
        messages=[{"role": "user", "content": text}],
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason != "end_turn":
        raise RuntimeError(f"model stopped with '{message.stop_reason}'")
    return message, json.loads(next(b.text for b in message.content if b.type == "text"))["explanations"]


def grounding(answer, smell_commits):
    """Commits the LLM cites for a smell that did not change the smell's files."""
    cited = {t["commit"] for t in answer["timeline"]} | ({answer["emerged_in"]} if answer["emerged_in"] else set())
    unknown = sorted(cited - set(smell_commits))
    return {"cited": len(cited), "unknown_commits": unknown, "grounded": not unknown}


def markdown(repo, smells):
    lines = [f"# How the architectural smells of {repo} emerged", ""]
    for n, s in enumerate(smells, 1):
        d, a = s["designite"], s.get("answer")
        lines += [f"## {n}. {d['Smell']} in {d['Namespace']} ({d['Project']})", "",
                  f"**Designite:** {d['Description']}", "",
                  f"**Classes:** {d['Participating classes']}", "",
                  f"**Commits that changed its files:** {len(s['commits'])}", ""]
        if not a:
            lines += [f"_No explanation: {s['error']}_", ""]
            continue
        lines += [f"**Emerged in:** {a['emerged_in'] or 'unknown'} {a['emerged_date']}", "",
                  f"**How:** {a['how']}", "", "**Timeline:**", ""]
        lines += [f"- `{t['commit']}`: {t['change']}" for t in a["timeline"]] or ["- none"]
        lines += ["", f"**Why it is a problem:** {a['why_problematic']}", ""]
        if not s["grounding"]["grounded"]:
            lines += [f"_Cites commits that did not change its files: {', '.join(s['grounding']['unknown_commits'])}_", ""]
    return "\n".join(lines)


def main(selected, dry_run):
    with open(ROOT / "data" / "subjects.csv", newline="") as f:
        subjects = {s["repo"]: s for s in csv.DictReader(f)}
    client = None if dry_run else anthropic.Anthropic()

    for repo in selected:
        print(repo)
        subject, name = subjects.get(repo), repo.replace("/", "_")
        repo_dir = ROOT / "repos" / name
        if not subject:
            print("    not in data/subjects.csv, skipped")
            continue
        if not repo_dir.is_dir() or not (ROOT / "output" / "designite" / name).is_dir():
            print("    not in repos/ or no Designite results - run scripts/analyze.sh first, skipped")
            continue
        declared = class_files(repo_dir, projects(repo_dir))
        out = OUT / name
        (out / "prompts").mkdir(parents=True, exist_ok=True)

        # the smells of each project, with the files declaring their participating classes
        groups = {}
        for d in sorted(designite(name)[0], key=lambda d: (d["Project"], d["Namespace"], d["Smell"])):
            classes = [c.strip().split(".")[-1] for c in d["Participating classes"].split(";") if c.strip()]
            in_project = declared.get(d["Project"], {})
            files = sorted(set().union(*(in_project.get(c, set()) for c in classes)))
            if not files:
                print(f"    {d['Smell']} in {d['Namespace']}: no files found for its classes, skipped")
                continue
            groups.setdefault(d["Project"], []).append({"designite": d, "files": files})

        all_smells, calls = [], []
        for project, smells in groups.items():
            commits = history(repo_dir, subject["commit"], set().union(*(s["files"] for s in smells)))
            for s in smells:
                s["commits"] = [c["commit"] for c in commits if set(c["files"]) & set(s["files"])]
            all_smells += smells
            text = prompt(project, smells, commits)
            prompt_file = out / "prompts" / (re.sub(r"[^\w.-]", "_", project) + ".md")
            prompt_file.write_text(text + "\n", encoding="utf-8")
            label = f"    {project}: {len(smells)} smells, {len(commits)} commits, {len(text)} chars"
            if dry_run:
                print(label)
                continue
            try:
                message, answers = explain(client, text)
            except (anthropic.APIError, RuntimeError) as e:
                print(f"{label}: LLM failed: {e}")
                for s in smells:
                    s["error"] = str(e)
                continue
            by_id = {a["smell_id"]: a for a in answers}
            for i, s in enumerate(smells, 1):
                if i in by_id:
                    s.update(answer=by_id[i], grounding=grounding(by_id[i], s["commits"]))
                else:
                    s["error"] = "the LLM gave no explanation for this smell"
            calls.append({"project": project, "prompt": prompt_file.relative_to(out).as_posix(),
                          "commits": commits, "usage": message.usage.model_dump()})
            answered = [s for s in smells if "answer" in s]
            print(f"{label}: {len(answered)}/{len(smells)} explained, "
                  f"{sum(s['grounding']['grounded'] for s in answered)} grounded")

        if not dry_run:
            (out / "explanations.json").write_text(json.dumps(
                {"repo": repo, "commit": subject["commit"], "model": MODEL, "effort": EFFORT,
                 "smells": all_smells, "calls": calls}, indent=2), encoding="utf-8")
            (out / "explanations.md").write_text(markdown(repo, all_smells), encoding="utf-8")
        print(f"    -> {out.relative_to(ROOT).as_posix()}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="+", help="owner/repo as in data/subjects.csv")
    parser.add_argument("--dry-run", action="store_true", help="only write the prompts, without calling the LLM")
    args = parser.parse_args()
    main(args.repos, args.dry_run)
