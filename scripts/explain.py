"""Asks an LLM agent to explain how and when each architectural smell found by Designite emerged (RQ2).
One agent session per project: the LLM gets all Designite smells of the project (with their participating classes and
the files declaring them) and the smell definitions from prompts/arch_smells.md, but no history. It explores the git
history itself with read-only tools (git_log, git_show, read_file, list_files, grep), limited to the analyzed commit
and its ancestors, and ends by calling submit_explanations. prompts/explain_smell.md is the system prompt.
Designite reports Dense Structure for "<All projects included>", so it gets its own session.
Every commit the LLM cites for a smell is checked: grounded = it exists in the analyzed history; citing commits that
did not change the smell's files is allowed (a smell can emerge through other files) but recorded.
Needs:   repos cloned by scripts/analyze.sh, Designite results in output/designite/, and ANTHROPIC_API_KEY in .env
Usage:   python scripts/explain.py owner/repo [...]              explain the smells of the given repos
         python scripts/explain.py --dry-run owner/repo [...]    only write the first message of each session
Output:  output/explanations/<owner>_<repo>/explanations.json   per smell: Designite's finding, its files and commits,
                                                                the LLM's answer and the grounding check; per session:
                                                                every step (text and tool calls) and token usage
         output/explanations/<owner>_<repo>/explanations.md     the same, readable, e.g. for developers to rate
         output/explanations/<owner>_<repo>/prompts/<project>.md  the first message of each session
"""
import argparse
import csv
import json
import re
import subprocess
from collections import Counter

import anthropic

from compare import designite
from llm_analyze import EFFORT, MODEL, ROOT, projects

OUT = ROOT / "output" / "explanations"
SYSTEM = (ROOT / "prompts" / "explain_smell.md").read_text(encoding="utf-8")
DEFINITIONS = (ROOT / "prompts" / "arch_smells.md").read_text(encoding="utf-8")
ALL_PROJECTS = "<All projects included>"   # Designite's project for Dense Structure
MAX_STEPS = 60              # model turns per session; a session that has not submitted by then fails
MAX_RESULT_CHARS = 40_000   # characters per tool result; longer results are cut off with a hint to narrow them
PAGE_LINES = 500            # lines per call of read_file and of git_show with a path; more via start_line
USAGE = ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"]
EXPLANATION = {
    "type": "object",
    "additionalProperties": False,
    "required": ["smell_id", "emerged_in", "emerged_date", "how", "timeline", "why_problematic"],
    "properties": {
        "smell_id": {"type": "integer"},
        "emerged_in": {"type": "string", "description": "short hash of the commit the smell last emerged in, or empty"},
        "emerged_date": {"type": "string"},
        "how": {"type": "string"},
        "timeline": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["commit", "change"],
            "properties": {"commit": {"type": "string"}, "change": {"type": "string"}}}},
        "why_problematic": {"type": "string"},
    },
}


def tool(name, description, **properties):
    """A strict tool definition whose parameters are all required."""
    return {"name": name, "description": description, "strict": True,
            "input_schema": {"type": "object", "properties": properties, "required": list(properties),
                             "additionalProperties": False}}


COMMIT = {"type": "string", "description": "short hash of the analyzed commit or one of its ancestors (e.g. abc1234~1)"}
PATH = {"type": "string", "description": "repo-relative path of a file or directory, or empty for the whole repo"}
START = {"type": "integer", "description": "first line to show, 1 for the start"}
TOOLS = [
    tool("git_log", "List the commits up to the analyzed version, oldest first (merge commits excluded): short hash, "
                    "date and message header. With a path, only the commits that changed it.", path=PATH),
    tool("git_show", "Show one commit. Without a path: its full message and the files it changed with line counts. "
                     f"With a file path: its diff of that file, {PAGE_LINES} lines at a time from start_line.",
         commit=COMMIT, path=PATH, start_line=START),
    tool("read_file", f"Show a file as it was at a commit, with line numbers, {PAGE_LINES} lines at a time from "
                      "start_line.", commit=COMMIT, path={"type": "string", "description": "repo-relative file path"},
         start_line=START),
    tool("list_files", "List the files that existed at a commit, optionally only below a directory.",
         commit=COMMIT, path=PATH),
    tool("grep", "Search the files as they were at a commit for a regular expression (git grep -E); shows "
                 "path:line:text for each match.", commit=COMMIT,
         pattern={"type": "string", "description": "extended regular expression"}, path=PATH),
    tool("submit_explanations", "Submit the explanations of all smells. Call this once, at the end.",
         explanations={"type": "array", "items": EXPLANATION}),
]


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


def smell_files(declared, d):
    """The repo-relative paths of the .cs files declaring the participating classes of Designite row `d`."""
    classes = [c.strip().split(".")[-1] for c in d["Participating classes"].split(";") if c.strip()]
    in_project = declared.get(d["Project"], {})
    return sorted(set().union(*(in_project.get(c, set()) for c in classes)))


def revision(repo_dir, commit, rev):
    """The full hash of `rev` if it is the analyzed `commit` or one of its ancestors; ValueError otherwise."""
    if not rev or rev.startswith("-"):
        raise ValueError(f"invalid commit '{rev}'")
    try:
        sha = git(repo_dir, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").strip()
    except subprocess.CalledProcessError:
        raise ValueError(f"unknown commit '{rev}'")
    try:
        git(repo_dir, "merge-base", "--is-ancestor", sha, commit)
    except subprocess.CalledProcessError:
        raise ValueError(f"commit '{rev}' is after the analyzed version {commit[:10]}; only it and its ancestors "
                         "can be used")
    return sha


def page(lines, start_line):
    """`PAGE_LINES` of `lines` from `start_line` (1-based), with a note if there are more."""
    start = max(start_line, 1)
    shown = lines[start - 1:start - 1 + PAGE_LINES]
    text = "\n".join(shown)
    end = start - 1 + len(shown)
    if end < len(lines):
        text += f"\n... (lines {start}-{end} of {len(lines)}; call again with start_line={end + 1} for more)"
    return text


def run_tool(repo_dir, commit, name, args):
    """The result of tool `name` on the repo at the analyzed `commit`; ValueError or CalledProcessError on failure."""
    path = args.get("path", "").strip().lstrip("/").removeprefix("./")
    paths = ["--", path] if path else []
    if name == "git_log":
        return git(repo_dir, "log", "--reverse", "--no-merges", "--format=%h %ad %s", "--date=short", "--abbrev=10",
                   commit, *paths) or "no commits"
    sha = revision(repo_dir, commit, args["commit"])
    if name == "git_show" and not path:
        return git(repo_dir, "show", "--stat=1000", "--format=commit %h, %ad%n%n%B", "--date=short", "--abbrev=10", sha)
    if name == "git_show":
        diff = git(repo_dir, "show", "--format=", "--no-color", sha, "--", path)
        return page(diff.splitlines(), args["start_line"]) if diff else f"commit did not change {path}"
    if name == "read_file":
        lines = git(repo_dir, "show", f"{sha}:{path}").splitlines()
        return page([f"{i:5}  {line}" for i, line in enumerate(lines, 1)], args["start_line"])
    if name == "list_files":
        return git(repo_dir, "ls-tree", "-r", "--name-only", sha, *paths) or "no files"
    if name == "grep":
        try:
            return git(repo_dir, "grep", "-n", "-I", "-E", "-e", args["pattern"], sha, *paths).replace(f"{sha}:", "")
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                return "no matches"
            raise
    raise ValueError(f"unknown tool '{name}'")


def first_message(project, smells, commit):
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
    parts.append(f"The analyzed version is commit {commit[:10]}. Explain for each smell above how and when it emerged.")
    return "\n".join(parts)


def explore(client, text, system, tools, run, submit, nudge, max_steps=MAX_STEPS):
    """Runs one agent session: `run(name, input)` executes a tool call and returns its result. It ends when the model
    calls the tool `submit`; `nudge` asks for that if the model stops without it.
    Returns (the input of the `submit` call, the steps taken, the summed token usage)."""
    messages, steps, usage = [{"role": "user", "content": text}], [], Counter()
    for _ in range(max_steps):
        with client.messages.stream(
            model=MODEL,
            max_tokens=64000,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            cache_control={"type": "ephemeral"},   # caches the growing conversation between steps
        ) as stream:
            message = stream.get_final_message()
        usage.update({k: getattr(message.usage, k) or 0 for k in USAGE})
        messages.append({"role": "assistant", "content": message.content})
        step = {"text": "\n".join(b.text for b in message.content if b.type == "text"), "calls": []}
        steps.append(step)
        calls = [b for b in message.content if b.type == "tool_use"]
        if not calls:
            if message.stop_reason != "end_turn":
                raise RuntimeError(f"model stopped with '{message.stop_reason}'")
            messages.append({"role": "user", "content": nudge})
            continue
        results = []
        for call in calls:
            if call.name == submit:
                step["calls"].append({"tool": call.name})
                return call.input, steps, dict(usage)
            try:
                result, error = run(call.name, call.input), False
            except (ValueError, OSError) as e:
                result, error = f"Error: {e}", True
            except subprocess.CalledProcessError as e:
                result, error = f"Error: {e.stderr.strip() or 'git failed'}", True
            if len(result) > MAX_RESULT_CHARS:
                result = (result[:MAX_RESULT_CHARS] + f"\n... (output cut off after {MAX_RESULT_CHARS} characters; "
                          "narrow it down with a path or a more specific pattern)")
            step["calls"].append({"tool": call.name, "input": call.input, "result_chars": len(result), "error": error})
            results.append({"type": "tool_result", "tool_use_id": call.id, "content": result, "is_error": error})
        messages.append({"role": "user", "content": results})
    raise RuntimeError(f"nothing submitted after {max_steps} steps")


def changing_commits(repo_dir, commit, files):
    """{full hash of each non-merge commit up to `commit` that changed `files`: the given files it changed}."""
    log = git(repo_dir, "log", "--no-merges", "--name-only", "--format=@@%H", commit, "--", *sorted(files))
    return {sha: set(changed) & files for sha, *changed in (b.strip().splitlines() for b in log.split("@@")[1:])}


def grounding(answer, repo_dir, commit, smell_commits):
    """Commits the LLM cites for a smell: those not in the analyzed history (unknown), and those in it that did not
    change the smell's files (`smell_commits`, full hashes)."""
    cited = {t["commit"] for t in answer["timeline"]} | ({answer["emerged_in"]} if answer["emerged_in"] else set())
    resolved = {}
    for c in cited:
        try:
            resolved[c] = revision(repo_dir, commit, c)
        except ValueError:
            pass
    return {"cited": len(cited), "unknown_commits": sorted(cited - resolved.keys()),
            "other_commits": sorted(c for c, sha in resolved.items() if sha not in smell_commits),
            "grounded": len(resolved) == len(cited)}


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
        g = s["grounding"]
        if g["unknown_commits"]:
            lines += [f"_Cites commits that are not in the analyzed history: {', '.join(g['unknown_commits'])}_", ""]
        if g["other_commits"]:
            lines += [f"_Cites commits that did not change its files: {', '.join(g['other_commits'])}_", ""]
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
        commit = git(repo_dir, "rev-parse", subject["commit"]).strip()
        declared = class_files(repo_dir, projects(repo_dir))
        out = OUT / name
        (out / "prompts").mkdir(parents=True, exist_ok=True)

        # the smells of each project, with the files declaring their participating classes
        groups = {}
        for d in sorted(designite(name)[0], key=lambda d: (d["Project"], d["Namespace"], d["Smell"])):
            files = smell_files(declared, d)
            if not files:
                print(f"    {d['Smell']} in {d['Namespace']}: no files found for its classes, skipped")
                continue
            groups.setdefault(d["Project"], []).append({"designite": d, "files": files})

        all_smells, sessions = [], []
        for project, smells in groups.items():
            changed = changing_commits(repo_dir, commit, set().union(*(s["files"] for s in smells)))
            for s in smells:
                s["commits"] = [sha[:10] for sha, files in changed.items() if files & set(s["files"])]
            all_smells += smells
            text = first_message(project, smells, commit)
            prompt_file = out / "prompts" / (re.sub(r"[^\w.-]", "_", project) + ".md")
            prompt_file.write_text(text + "\n", encoding="utf-8")
            label = f"    {project}: {len(smells)} smells"
            if dry_run:
                print(label)
                continue
            try:
                submitted, steps, usage = explore(
                    client, text, SYSTEM, TOOLS, lambda tool_name, args: run_tool(repo_dir, commit, tool_name, args),
                    "submit_explanations", "Submit your explanations of all smells with submit_explanations.")
            except (anthropic.APIError, RuntimeError) as e:
                print(f"{label}: LLM failed: {e}")
                for s in smells:
                    s["error"] = str(e)
                continue
            by_id = {a["smell_id"]: a for a in submitted["explanations"]}
            for i, s in enumerate(smells, 1):
                if i in by_id:
                    smell_commits = {sha for sha, files in changed.items() if files & set(s["files"])}
                    s.update(answer=by_id[i], grounding=grounding(by_id[i], repo_dir, commit, smell_commits))
                else:
                    s["error"] = "the LLM gave no explanation for this smell"
            sessions.append({"project": project, "prompt": prompt_file.relative_to(out).as_posix(),
                             "steps": steps, "usage": usage})
            answered = [s for s in smells if "answer" in s]
            print(f"{label}: {len(answered)}/{len(smells)} explained, "
                  f"{sum(s['grounding']['grounded'] for s in answered)} grounded, {len(steps)} steps, "
                  f"{sum(len(st['calls']) for st in steps)} tool calls")

        if not dry_run:
            (out / "explanations.json").write_text(json.dumps(
                {"repo": repo, "commit": subject["commit"], "model": MODEL, "effort": EFFORT,
                 "smells": all_smells, "sessions": sessions}, indent=2), encoding="utf-8")
            (out / "explanations.md").write_text(markdown(repo, all_smells), encoding="utf-8")
        print(f"    -> {out.relative_to(ROOT).as_posix()}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="+", help="owner/repo as in data/subjects.csv")
    parser.add_argument("--dry-run", action="store_true", help="only write the first message of each session")
    args = parser.parse_args()
    main(args.repos, args.dry_run)
