"""Asks an LLM agent to refactor all architectural smells Designite found in a repo, and checks the result (RQ3).
One agent session per repo, for all its smells at once, in a git worktree at the analyzed commit. The agent gets every
smell (Designite's finding, participating classes and the files declaring them), the smells' definitions and what a
component and a dependency are (prompts/arch_smells.md), and with --with-explanation also how each smell emerged (RQ2,
scripts/explain.py). It reads and edits the code with list_files, read_file, grep, edit_file, write_file and
delete_file, can call build and, if the solution has test projects, run_tests, and ends with submit_refactoring: a
summary, and per smell the refactorings applied, the steps and a rationale. prompts/refactor_smell.md is the system
prompt. Designite is not available to the agent.
Its changes are committed in the worktree and checked once:
  1. builds          dotnet build of the solution succeeds
  2. tests_pass      dotnet test succeeds; no_tests if the solution has no test project, failing_before if the tests
                     already fail at the analyzed commit
  3. smell_removed   per smell: Designite no longer finds it (the same smell as in verify.py: smell, project and
                     namespace, and for Cyclic Dependency and Scattered Functionality the components)
  4. new smells      smells Designite finds after the refactoring but not at the analyzed commit: one row each
Needs:   Windows (Designite), the .NET SDK, tools/designite/DesigniteConsole.dll, repos cloned and Designite results from
         scripts/analyze.sh, ANTHROPIC_API_KEY in .env, and for --with-explanation the results of scripts/explain.py
Usage:   python scripts/refactor.py owner/repo [...]                      refactor the smells of the given repos
         python scripts/refactor.py --with-explanation owner/repo [...]   the same, with how each smell emerged
         python scripts/refactor.py --dry-run owner/repo [...]            only write the first message of the session
Output:  output/refactoring/<variant>/<owner>_<repo>/, variant: code, or explanation with --with-explanation
           refactoring.csv      one row per smell and per new smell, see COLUMNS
           refactorings.json    the LLM's summary; per smell Designite's finding, the LLM's answer and the checks; the
                                new smells; every step of the session (text and tool calls) and token usage
           refactorings.md      the same, readable
           refactoring.patch    the code changes
           prompt.md            the first message of the session
           designite/<commit>/  Designite's results at the analyzed commit and after the refactoring
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess

import anthropic

from compare import designite
from explain import DEFINITIONS, PAGE_LINES, START, class_files, definition, explore, git, page, smell_files, tool
from llm_analyze import EFFORT, MODEL, ROOT, projects
from verify import DESIGNITE_DIR, key, remove_worktree, smells_at

OUT = ROOT / "output" / "refactoring"
EXPLANATIONS = ROOT / "output" / "explanations"
SYSTEM = (ROOT / "prompts" / "refactor_smell.md").read_text(encoding="utf-8")
UNIT = re.search(r"^# Unit of analysis\n(.*?)(?=^#)", DEFINITIONS, re.M | re.S).group(1).strip()
MAX_STEPS = 200             # model turns per session; a session that has not submitted by then fails
DOTNET_TIMEOUT = 20 * 60    # seconds per dotnet build or test
TEST_PROJECT = re.compile(r"Microsoft\.NET\.Test\.Sdk|<IsTestProject>\s*true|xunit|nunit|mstest", re.I)
REFACTORINGS = ["Move Class", "Move Method", "Extract Class", "Extract Component", "Split Component",
                "Merge Components", "Invert Dependency", "Replace Type with Data", "Consolidate Duplicate Logic",
                "Make Interface Explicit", "Other"]   # the catalog in prompts/refactor_smell.md
COLUMNS = {
    "id": "number of the smell in the prompt; empty for a new smell", "smell": "", "project": "", "namespace": "",
    "description": "Designite's description: at the analyzed commit, or after the refactoring for a new smell",
    "refactoring_type": "the refactorings the LLM applied for this smell, from the catalog in prompts/refactor_smell.md",
    "builds": "yes or no: dotnet build succeeds after the refactoring (the same for all rows)",
    "tests_pass": "yes, no, no_tests (no test project) or failing_before (the tests fail at the analyzed commit); "
                  "the same for all rows",
    "smell_removed": "yes or no: Designite no longer finds the smell; empty if Designite failed, and for new smells",
    "verdict": "fixed, not_fixed, tests_fail, broken_build, unverifiable (Designite failed on the refactored code), "
               "not_reproduced (Designite does not find the smell at the analyzed commit in this run; not given to "
               "the LLM), no_answer (the session failed, or the LLM did not answer this smell) or new_smell (found "
               "after the refactoring but not at the analyzed commit)",
}

FILE = {"type": "string", "description": "repo-relative file path"}
DIR = {"type": "string", "description": "repo-relative directory, or empty for the whole repo"}
TEXT = {"type": "string"}
ANSWER = {
    "type": "object",
    "additionalProperties": False,
    "required": ["smell_id", "refactorings", "steps", "rationale"],
    "properties": {
        "smell_id": {"type": "integer"},
        "refactorings": {"type": "array", "items": {"type": "string", "enum": REFACTORINGS}},
        "steps": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
}
TOOLS = [
    tool("list_files", "List the files of the working copy (without .git, bin and obj), optionally only below a "
                       "directory.", path=DIR),
    tool("read_file", f"Show a file of the working copy with line numbers, {PAGE_LINES} lines at a time from "
                      "start_line.", path=FILE, start_line=START),
    tool("grep", "Search the files of the working copy for a regular expression (git grep -E); shows path:line:text "
                 "for each match.", pattern={"type": "string", "description": "extended regular expression"}, path=DIR),
    tool("edit_file", "Replace old_text with new_text in a file. old_text must occur exactly once in the file, with "
                      "the same whitespace and indentation; include enough surrounding lines to make it unique.",
         path=FILE, old_text=TEXT, new_text=TEXT),
    tool("write_file", "Create a file, or replace a file's whole content. Directories are created as needed.",
         path=FILE, content=TEXT),
    tool("delete_file", "Delete a file, e.g. after its type moved to another file.", path=FILE),
    tool("build", "Build the solution with dotnet build. Shows the compiler errors, or that the build succeeded."),
    tool("run_tests", "Run the solution's tests with dotnet test. Shows the output if a test fails, or that all "
                      "tests passed."),
    tool("submit_refactoring", "Submit the refactoring of all smells. Call this once, at the end, after your last "
                               "change.", summary=TEXT, smells={"type": "array", "items": ANSWER}),
]


# --- the working copy --------------------------------------------------------------------------------------------

def resolve(worktree, path):
    """The absolute path of repo-relative `path` in the worktree; ValueError if it leaves the worktree or is in .git."""
    p = (worktree / path.strip().lstrip("/").removeprefix("./")).resolve()
    if not p.is_relative_to(worktree) or ".git" in p.relative_to(worktree).parts:
        raise ValueError(f"'{path}' is outside the working copy")
    return p


def read(p):
    """(text with \\n line ends, the file's line end, whether it starts with a UTF-8 BOM)."""
    raw = p.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n"), "\r\n" if "\r\n" in text else "\n", raw.startswith(b"\xef\xbb\xbf")


def write(p, text, newline="\n", bom=False):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.replace("\r\n", "\n").replace("\n", newline).encode("utf-8"))


def dotnet(worktree, command, sln):
    """Runs `dotnet build` or `dotnet test` on the solution. Returns (succeeded, output). No MSBuild nodes stay
    behind (-nodeReuse:false), so they cannot keep files of the worktree open."""
    try:
        done = subprocess.run(["dotnet", command, str(sln), "-nologo", "-nodeReuse:false"], cwd=worktree,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              stdin=subprocess.DEVNULL, timeout=DOTNET_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, f"dotnet {command} timed out after {DOTNET_TIMEOUT // 60} minutes"
    return done.returncode == 0, (done.stdout + done.stderr).replace(str(worktree) + os.sep, "")


def run_tool(worktree, sln, name, args):
    """The result of tool `name` on the working copy; ValueError, OSError or CalledProcessError on failure."""
    if name == "list_files":
        base = resolve(worktree, args["path"])
        files = (p.relative_to(worktree) for p in base.rglob("*") if p.is_file())
        return "\n".join(sorted(f.as_posix() for f in files if not {".git", "bin", "obj"} & set(f.parts))) or "no files"
    if name == "grep":
        path = args["path"].strip()
        try:
            return git(worktree, "grep", "-n", "-I", "-E", "--untracked", "-e", args["pattern"],
                       *(["--", path] if path else []))
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                return "no matches"
            raise
    if name == "build":
        ok, output = dotnet(worktree, "build", sln)
        errors = dict.fromkeys(line.strip() for line in output.splitlines() if re.search(r"\berror\b", line))
        return "Build succeeded." if ok else "\n".join(errors) or output
    if name == "run_tests":
        ok, output = dotnet(worktree, "test", sln)
        return "All tests passed." if ok else "\n".join(output.splitlines()[-200:])
    p, path = resolve(worktree, args["path"]), args["path"]
    if name == "read_file":
        lines = read(p)[0].splitlines()
        return page([f"{i:5}  {line}" for i, line in enumerate(lines, 1)], args["start_line"])
    if name == "edit_file":
        text, newline, bom = read(p)
        old = args["old_text"].replace("\r\n", "\n")
        if text.count(old) != 1:
            raise ValueError(f"old_text occurs {text.count(old)} times in {path}; it must occur exactly once")
        write(p, text.replace(old, args["new_text"]), newline, bom)
        return f"edited {path}"
    if name == "write_file":
        write(p, args["content"], *(read(p)[1:] if p.is_file() else ()))
        return f"wrote {path}"
    if name == "delete_file":
        p.unlink()
        return f"deleted {path}"
    raise ValueError(f"unknown tool '{name}'")


def checkout(worktree, sha):
    git(worktree, "checkout", "-q", "--force", "--detach", sha)
    git(worktree, "clean", "-fdxq")


def commit_changes(worktree, message):
    """Commits everything the agent changed (without build output). Returns the new commit's full hash."""
    git(worktree, "add", "-A", "--", ".", ":(exclude,glob)**/bin/**", ":(exclude,glob)**/obj/**")
    git(worktree, "-c", "user.name=refactor.py", "-c", "user.email=refactor.py@localhost",
        "commit", "-q", "--allow-empty", "--no-verify", "-m", message)
    return git(worktree, "rev-parse", "HEAD").strip()


def has_tests(sln):
    """Whether the solution contains a test project."""
    for csproj in re.findall(r'"([^"]+\.csproj)"', sln.read_text(encoding="utf-8-sig", errors="replace")):
        p = sln.parent / csproj.replace("\\", "/")
        if p.is_file() and TEST_PROJECT.search(p.read_text(encoding="utf-8-sig", errors="replace")):
            return True
    return False


# --- the session and its checks ----------------------------------------------------------------------------------

def first_message(smells, sln, tests):
    parts = ["<smells>"]
    for s in smells:
        d, how = s["designite"], s.get("explanation")
        parts += [f'<smell id="{s["id"]}">',
                  f"Smell: {d['Smell']}",
                  f"Project: {d['Project']}",
                  f"Component: {d['Namespace']}",
                  f"Designite's finding: {d['Description']}",
                  f"Participating classes: {d['Participating classes']}",
                  "Files: " + ", ".join(s["files"])]
        if how:
            parts.append(f"How it emerged: {how['how']}\nWhy it is a problem: {how['why_problematic']}")
        parts.append("</smell>")
    parts.append("</smells>")
    parts.append("<definitions>")
    for name in dict.fromkeys(s["designite"]["Smell"] for s in smells):
        # without the reporting rules for detection ("Report one instance ...")
        parts.append(f"## {name}\n{definition(name).split(chr(10) + 'Report')[0].strip()}")
    parts.append("</definitions>")
    parts.append(f"<components_and_dependencies>\n{UNIT}\n</components_and_dependencies>")
    parts.append(f"The solution is {sln}. It has {'test projects' if tests else 'no test projects'}.")
    parts.append("Refactor the code so that the smells above are removed.")
    return "\n".join(parts)


def row_of(d, **values):
    row = dict.fromkeys(COLUMNS, "")
    row.update(smell=d["Smell"], project=d["Project"], namespace=d["Namespace"], description=d["Description"])
    return {**row, **values}


def verdict(row):
    if row["builds"] == "no":
        return "broken_build"
    if row["tests_pass"] == "no":
        return "tests_fail"
    if not row["smell_removed"]:
        return "unverifiable"
    return "fixed" if row["smell_removed"] == "yes" else "not_fixed"


def refactor(client, smells, text, worktree, commit, sln, tests, before, cache, out):
    """Runs the agent session for all `smells`, commits and checks its changes. Adds each smell's answer and checks to
    it. Returns (the rows of refactoring.csv, the session: summary, new smells, steps and usage, or error)."""
    rows = [row_of(s["designite"], id=s["id"], verdict="not_reproduced") for s in smells if not s["reproduced"]]
    given = [s for s in smells if s["reproduced"]]
    if not given:
        return rows, {"error": "no smell reproduced"}

    def progress(number, step):
        print(f"    step {number}: " + (", ".join(c["tool"] for c in step["calls"]) or "text only"), flush=True)

    checkout(worktree, commit)
    tools = TOOLS if tests else [t for t in TOOLS if t["name"] != "run_tests"]
    try:
        answer, steps, usage = explore(
            client, text, SYSTEM, tools, lambda name, args: run_tool(worktree, sln, name, args),
            "submit_refactoring", "Finish the refactoring and submit it with submit_refactoring.", MAX_STEPS, progress)
    except (anthropic.APIError, RuntimeError) as e:
        print(f"    LLM failed: {e}")
        for s in given:
            s["error"] = str(e)
        return rows + [row_of(s["designite"], id=s["id"], verdict="no_answer") for s in given], {"error": str(e)}

    sha = commit_changes(worktree, f"Refactor the architectural smells of {out.name}")
    (out / "refactoring.patch").write_text(git(worktree, "diff", commit, sha), encoding="utf-8")
    checkout(worktree, sha)
    builds = "yes" if dotnet(worktree, "build", sln)[0] else "no"
    tests_pass = ("no_tests" if tests is None else "failing_before" if not tests else
                  "yes" if dotnet(worktree, "test", sln)[0] else "no")
    after = smells_at(worktree, sha, cache)
    after_rows = designite(sha, base=cache)[0] if after is not None else []

    answers = {a["smell_id"]: a for a in answer["smells"]}
    for s in given:
        k = key(s["designite"])
        a = answers.get(s["id"])
        row = row_of(s["designite"], id=s["id"], builds=builds, tests_pass=tests_pass,
                     smell_removed="" if after is None else "no" if k in after else "yes")
        row["verdict"] = verdict(row) if a else "no_answer"
        if a:
            s["answer"] = a
            row["refactoring_type"] = "; ".join(a["refactorings"])
        else:
            s["error"] = "the LLM gave no answer for this smell"
        s["checks"] = {c: row[c] for c in ("builds", "tests_pass", "smell_removed", "verdict")}
        rows.append(row)
    new = [d for d in after_rows if key(d) not in before]
    rows += [row_of(d, builds=builds, tests_pass=tests_pass, verdict="new_smell") for d in new]
    return rows, {"summary": answer["summary"], "builds": builds, "tests_pass": tests_pass,
                  "designite_after": "failed" if after is None else "ok", "new_smells": new,
                  "steps": steps, "usage": usage}


def markdown(repo, variant, smells, session):
    lines = [f"# Refactoring of the architectural smells of {repo} ({variant})", ""]
    if "summary" not in session:
        return "\n".join(lines + [f"_No refactoring: {session.get('error')}_", ""])
    lines += [f"**Summary:** {session['summary']}", "",
              f"**Checks:** builds {session['builds']}, tests {session['tests_pass']}, "
              f"Designite after the refactoring {session['designite_after']}", "",
              "**Patch:** [refactoring.patch](refactoring.patch)", ""]
    for s in smells:
        d, a, c = s["designite"], s.get("answer"), s.get("checks", {})
        lines += [f"## {s['id']}. {d['Smell']} in {d['Namespace']} ({d['Project']})", "",
                  f"**Designite:** {d['Description']}", ""]
        if not a:
            lines += [f"_No refactoring: {s.get('error') or 'not reproduced by Designite'}_", ""]
            continue
        lines += [f"**Refactorings:** {', '.join(a['refactorings']) or 'none'}", "", "**Steps:**", ""]
        lines += [f"- {step}" for step in a["steps"]] or ["- none"]
        lines += ["", f"**Rationale:** {a['rationale']}", "",
                  f"**Smell removed:** {c.get('smell_removed') or 'unknown'} -> **{c.get('verdict')}**", ""]
    lines += ["## New smells", ""]
    lines += [f"- {d['Smell']} in {d['Namespace']} ({d['Project']}): {d['Description']}"
              for d in session["new_smells"]] or ["none"]
    return "\n".join(lines + [""])


# --- main --------------------------------------------------------------------------------------------------------

def main(selected, with_explanation, dry_run):
    if not dry_run and not (DESIGNITE_DIR / "DesigniteConsole.dll").is_file():
        raise SystemExit("Missing tools/designite/DesigniteConsole.dll - put Designite there.")
    with open(ROOT / "data" / "subjects.csv", newline="") as f:
        subjects = {s["repo"]: s for s in csv.DictReader(f)}
    variant = "explanation" if with_explanation else "code"
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
        explained = {}
        if with_explanation:
            file = EXPLANATIONS / name / "explanations.json"
            if not file.is_file():
                print("    no explanations - run scripts/explain.py first, skipped")
                continue
            explained = {key(s["designite"]): s["answer"]
                         for s in json.loads(file.read_text(encoding="utf-8"))["smells"] if s.get("answer")}
        slns = sorted(repo_dir.rglob("*.sln"), key=lambda p: (len(p.parts), str(p)))
        if not slns:
            print("    no .sln, skipped")
            continue
        commit = git(repo_dir, "rev-parse", subject["commit"]).strip()
        sln_path = slns[0].relative_to(repo_dir)
        out = OUT / variant / name
        out.mkdir(parents=True, exist_ok=True)
        (out / "refactoring.patch").unlink(missing_ok=True)

        # the smells, with the files declaring their participating classes
        declared = class_files(repo_dir, projects(repo_dir))
        smells = []
        for d in sorted(designite(name)[0], key=lambda d: (d["Project"], d["Namespace"], d["Smell"])):
            files = smell_files(declared, d)
            if not files:
                print(f"    {d['Smell']} in {d['Namespace']}: no files found for its classes, skipped")
                continue
            if with_explanation and key(d) not in explained:
                print(f"    {d['Smell']} in {d['Namespace']}: no explanation, given without it")
            smells.append({"id": len(smells) + 1, "designite": d, "files": files, "explanation": explained.get(key(d)),
                           "reproduced": True})
        tests = has_tests(slns[0])
        if dry_run:
            (out / "prompt.md").write_text(first_message(smells, sln_path.as_posix(), tests) + "\n", encoding="utf-8")
            print(f"    {len(smells)} smells -> {(out / 'prompt.md').relative_to(ROOT).as_posix()}")
            continue

        worktree = ROOT / "repos" / f"{name}.refactor"
        shutil.rmtree(worktree, ignore_errors=True)
        git(repo_dir, "worktree", "prune")
        git(repo_dir, "worktree", "add", "-q", "--detach", str(worktree), commit)
        worktree, cache = worktree.resolve(), out / "designite"
        sln = worktree / sln_path
        try:
            # Designite and the build at the analyzed commit; its tests (None: no tests) decide what tests_pass means
            before = smells_at(worktree, commit, cache)
            checkout(worktree, commit)
            if before is None or not dotnet(worktree, "build", sln)[0]:
                print("    Designite or dotnet build fails at the analyzed commit, skipped")
                continue
            tests = dotnet(worktree, "test", sln)[0] if tests else None
            for s in smells:
                s["reproduced"] = key(s["designite"]) in before
            text = first_message([s for s in smells if s["reproduced"]], sln_path.as_posix(), tests is not None)
            (out / "prompt.md").write_text(text + "\n", encoding="utf-8")
            print(f"    {sum(s['reproduced'] for s in smells)}/{len(smells)} smells reproduced, refactoring them")
            rows, session = refactor(client, smells, text, worktree, commit, sln, tests, before, cache, out)
        finally:
            remove_worktree(repo_dir, worktree)
        rows.sort(key=lambda r: (r["id"] == "", r["id"] or 0))   # the smells by id, then the new smells

        with open(out / "refactoring.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(COLUMNS), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        (out / "refactorings.json").write_text(json.dumps(
            {"repo": repo, "commit": subject["commit"], "variant": variant, "model": MODEL, "effort": EFFORT,
             "tests_at_analyzed_commit": {None: "no_tests", True: "pass", False: "fail"}[tests],
             "smells": smells, "session": session}, indent=2), encoding="utf-8")
        (out / "refactorings.md").write_text(markdown(repo, variant, smells, session), encoding="utf-8")
        for r in rows:
            print(f"    {r['id'] or '-'}. {r['smell']} in {r['namespace']}: {r['verdict']}")
        fixed = sum(r["verdict"] == "fixed" for r in rows)
        new = sum(r["verdict"] == "new_smell" for r in rows)
        print(f"    {fixed}/{len(smells)} fixed, {new} new smells -> {out.relative_to(ROOT).as_posix()}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="+", help="owner/repo as in data/subjects.csv")
    parser.add_argument("--with-explanation", action="store_true",
                        help="also give the LLM how each smell emerged (output/explanations/, scripts/explain.py)")
    parser.add_argument("--dry-run", action="store_true", help="only write the first message of the session")
    args = parser.parse_args()
    main(args.repos, args.with_explanation, args.dry_run)
