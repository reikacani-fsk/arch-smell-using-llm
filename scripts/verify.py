"""Checks with Designite the commit in which the LLM says each smell last emerged (output/explanations/, RQ2).
The smell Designite finds at the analyzed commit last emerged in the oldest commit of the unbroken run, back from the
analyzed commit, in which Designite finds it. For each smell the script walks back from the analyzed commit through
the commits that change C# code and lie between it and the LLM's commit, then checks the LLM's commit and its parent.
It stops at the first commit without the smell (the LLM's commit is too early), or at the parent: there the smell must
be gone (confirmed), otherwise the LLM's commit is too late. Older commits are never analyzed.
A smell found at another commit is the same smell if smell, project and namespace match (for Cyclic Dependency and
Scattered Functionality, also the components Designite lists).
Designite runs as in analyze.sh (restore first; if Designite then crashes, again without restore) in a temporary git
worktree, so repos/ stays at the analyzed commit. Results are cached per commit and shared by all smells. Commits
Designite fails on are skipped, except the LLM's commit and its parent (then the smell is unverifiable).
Needs:   Windows (Designite), tools/designite/DesigniteConsole.dll, and explanations from scripts/explain.py
Usage:   python scripts/verify.py                     all repos with explanations
         python scripts/verify.py owner/repo [...]    only the given repos
Output:  output/verification/<owner>_<repo>/verification.csv     one row per smell, see COLUMNS
         output/verification/<owner>_<repo>/designite/<commit>/  Designite's ArchSmells files and logs per commit
"""
import argparse
import csv
import json
import shutil
import subprocess

from compare import designite
from explain import git, revision
from llm_analyze import ROOT

EXPLANATIONS = ROOT / "output" / "explanations"
OUT = ROOT / "output" / "verification"
DESIGNITE_DIR = ROOT / "tools" / "designite"
CODE = ["*.cs", "*.csproj", "*.sln"]   # only commits changing these can change what Designite finds
RESTORE = True                         # as in analyze.sh
COLUMNS = {
    "smell": "", "project": "", "namespace": "",
    "description": "Designite's description at the analyzed commit (for Cyclic Dependency and Scattered Functionality "
                   "its components tell apart the smells of one namespace)",
    "llm_commit": "commit the LLM says the smell emerged in",
    "present_at": "smell found at llm_commit: yes, no, or empty if not analyzed (the walk stopped at a later commit)",
    "present_before": "smell found at the parent of llm_commit: yes, no, no parent, or empty if not analyzed",
    "verdict": "confirmed (found from the analyzed commit down to llm_commit, not at its parent), "
               "too_early (not found at some commit from llm_commit on), too_late (also found at the parent), "
               "not_reproduced (Designite does not find it at the analyzed commit in this run), "
               "unverifiable (Designite failed on llm_commit or its parent) "
               "or no_commit (no answer, or a commit outside the analyzed history)",
    "actual_commit": "commit the smell last emerged in, if known: llm_commit when confirmed, the oldest commit of the "
                     "unbroken run when too_early; empty otherwise (when too_late it is older than the parent)",
}


def key(row):
    """What identifies a smell across commits. A namespace can have several cycles and several scattered concerns:
    they differ in the components Designite lists ("... in the cycle are: A' B'" or "... the same concern: A' B'")."""
    components = frozenset()
    if row["Smell"] in ("Cyclic Dependency", "Scattered Functionality"):
        components = frozenset(c.strip(" .") for c in row["Description"].split(":")[-1].split("'"))
    return row["Smell"], row["Project"], row["Namespace"], components


def run_designite(worktree, sha, out):
    """Runs Designite on commit `sha` into `out`. Returns False if it failed; no .sln counts as no smells."""
    git(worktree, "checkout", "-q", "--force", "--detach", sha)
    git(worktree, "clean", "-fdxq")
    slns = sorted(worktree.rglob("*.sln"), key=lambda p: (len(p.parts), str(p)))
    if not slns:
        return True

    def attempt():
        log = out / "designite.log"
        with open(log, "w") as f:
            done = subprocess.run(["dotnet", "./DesigniteConsole.dll", "-i", str(slns[0]), "-o", str(out)],
                                  cwd=DESIGNITE_DIR, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        return done.returncode == 0 and "Exception occurred" not in log.read_text(errors="replace")

    if RESTORE:
        with open(out / "restore.log", "w") as f:
            subprocess.run(["dotnet", "restore", str(slns[0])], stdout=f, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL)
    if attempt():
        return True
    if RESTORE:   # some repos make Designite crash once restored: retry without the restore output
        git(worktree, "clean", "-fdxq")
        return attempt()
    return False


def remove_worktree(repo_dir, worktree):
    """Removes a temporary worktree. On Windows, dotnet's build servers keep files in it open, so they are stopped
    first. If it still cannot be removed, it is only reported: the next run deletes it before adding it again."""
    subprocess.run(["dotnet", "build-server", "shutdown"], capture_output=True, stdin=subprocess.DEVNULL)
    try:
        git(repo_dir, "worktree", "remove", "--force", str(worktree))
    except subprocess.CalledProcessError as e:
        shutil.rmtree(worktree, ignore_errors=True)
        git(repo_dir, "worktree", "prune")
        if worktree.exists():
            print(f"    could not remove {worktree}: {e.stderr.strip()}")


def smells_at(worktree, sha, cache):
    """The keys of the smells Designite finds at commit `sha`, or None if Designite failed. Cached in `cache`/<sha>/."""
    out = cache / sha
    if not (out / "done").exists() and not (out / "failed").exists():
        print(f"    Designite on {sha[:10]}")
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        ok = run_designite(worktree, sha, out)
        for f in out.iterdir():   # keep only what is needed
            if not f.name.endswith(("_ArchSmells.csv", ".log")):
                f.unlink()
        (out / ("done" if ok else "failed")).touch()
    if (out / "failed").exists():
        return None
    return {key(r) for r in designite(sha, base=cache)[0]}


def verify(smell, repo_dir, commit, at):
    """One row of verification.csv for `smell`, checked at the analyzed `commit`, back to the LLM's commit's parent."""
    d, answer = smell["designite"], smell.get("answer") or {}
    k = key(d)
    row = dict.fromkeys(COLUMNS, "")
    row.update(smell=d["Smell"], project=d["Project"], namespace=d["Namespace"], description=d["Description"],
               llm_commit=answer.get("emerged_in", ""))
    try:
        sha = revision(repo_dir, commit, row["llm_commit"])
    except ValueError:
        return {**row, "verdict": "no_commit"}

    # 1) from the analyzed commit down to the LLM's commit (newest first): the smell must be found at every commit.
    #    --ancestry-path: only commits that contain the LLM's commit
    later = git(repo_dir, "rev-list", "--ancestry-path", f"{sha}..{commit}", "--", *CODE).split()
    last_found = ""
    for c in dict.fromkeys([commit, *later, sha]):
        found = at(c)
        if found is None:
            if c == sha:
                return {**row, "verdict": "unverifiable"}
            continue   # Designite failed on a commit in between: skip it
        if k not in found:
            return {**row, "present_at": "no" if c == sha else "", "actual_commit": last_found[:10],
                    "verdict": "too_early" if last_found else "not_reproduced"}
        last_found = c
    row["present_at"] = "yes"

    # 2) the parent of the LLM's commit (the first parent for a merge): the smell must not be found there
    parent = git(repo_dir, "rev-list", "--parents", "-n", "1", sha).split()[1:2]
    if not parent:
        return {**row, "present_before": "no parent", "verdict": "confirmed", "actual_commit": sha[:10]}
    found = at(parent[0])
    if found is None:
        return {**row, "verdict": "unverifiable"}
    if k in found:
        return {**row, "present_before": "yes", "verdict": "too_late"}
    return {**row, "present_before": "no", "verdict": "confirmed", "actual_commit": sha[:10]}


def main(selected):
    if not (DESIGNITE_DIR / "DesigniteConsole.dll").is_file():
        raise SystemExit("Missing tools/designite/DesigniteConsole.dll - put Designite there.")
    names = [r.replace("/", "_") for r in selected] or \
            sorted(p.parent.name for p in EXPLANATIONS.glob("*/explanations.json"))

    for name in names:
        print(name)
        file, repo_dir = EXPLANATIONS / name / "explanations.json", ROOT / "repos" / name
        if not file.is_file() or not repo_dir.is_dir():
            print("    no explanations or not in repos/ - run scripts/explain.py first, skipped")
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        commit = git(repo_dir, "rev-parse", data["commit"]).strip()
        out = OUT / name
        cache = out / "designite"

        worktree = ROOT / "repos" / f"{name}.verify"
        shutil.rmtree(worktree, ignore_errors=True)
        git(repo_dir, "worktree", "prune")
        git(repo_dir, "worktree", "add", "-q", "--detach", str(worktree), commit)
        try:
            at = lambda sha: smells_at(worktree, sha, cache)
            rows = [verify(s, repo_dir, commit, at) for s in data["smells"]]
        finally:
            remove_worktree(repo_dir, worktree)

        with open(out / "verification.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(COLUMNS))
            w.writeheader()
            w.writerows(rows)
        confirmed = sum(r["verdict"] == "confirmed" for r in rows)
        print(f"    {confirmed}/{len(rows)} confirmed -> {out.relative_to(ROOT).as_posix()}/verification.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="*", help="owner/repo as in data/subjects.csv (default: all with explanations)")
    main(parser.parse_args().repos)
