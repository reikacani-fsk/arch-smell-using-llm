"""Checks with Designite the commit in which the LLM says each smell emerged (output/explanations/, RQ2).
For each smell, Designite runs on the LLM's commit and on its parent: the claim holds if the smell is absent at the
parent and present at the commit. The script also finds the actual emergence commit: going back from the analyzed
commit through the commits that change C# code, it is the oldest commit of the unbroken run in which Designite finds
the smell.
A smell found at another commit is the same smell if smell, project and namespace match (for Cyclic Dependency, also
the components in the cycle). The history is the list of non-merge commits that git log shows, newest first.
Designite runs as in analyze.sh (restore first; if Designite then crashes, again without restore) in a temporary git
worktree, so repos/ stays at the analyzed commit. Results are cached per commit.
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
    "llm_commit": "commit the LLM says the smell emerged in",
    "present_before": "smell found at the parent of llm_commit: yes, no, no parent, or failed (Designite failed)",
    "present_at": "smell found at llm_commit: yes, no or failed",
    "verdict": "confirmed (absent before, present at), already_present (LLM too late), not_present (LLM too early), "
               "unverifiable (Designite failed) or no_commit (no answer, or a commit outside the analyzed history)",
    "actual_commit": "oldest commit of the unbroken run up to the analyzed commit in which Designite finds the smell "
                     "(empty if Designite does not find it at the analyzed commit)",
    "distance": "commits changing C# code from llm_commit to actual_commit: + LLM too early, - LLM too late "
                "(0 with verdict confirmed = exact; 0 otherwise = llm_commit changed no C# code)",
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


def actual_commits(repo_dir, commit, keys, at):
    """{smell key: oldest commit of the unbroken run, back from `commit`, in which Designite finds the smell}."""
    history = git(repo_dir, "rev-list", "--no-merges", commit, "--", *CODE).split()
    actual, pending = {}, set(keys)
    for sha in dict.fromkeys([commit, *history]):
        if not pending:
            break
        found = at(sha)
        if found is None:   # Designite failed: skip this commit
            continue
        for k in list(pending):
            if k in found:
                actual[k] = sha
            else:
                pending.discard(k)
    return actual


def distance(repo_dir, sha, actual):
    """Commits changing C# code from `sha` to `actual`: positive if `actual` is later."""
    count = lambda a, b: int(git(repo_dir, "rev-list", "--count", "--no-merges", f"{a}..{b}", "--", *CODE))
    return count(sha, actual) - count(actual, sha)


def verify(smell, repo_dir, commit, actual, at):
    """One row of verification.csv."""
    d, answer = smell["designite"], smell.get("answer") or {}
    k = key(d)
    row = dict.fromkeys(COLUMNS, "")
    row.update(smell=d["Smell"], project=d["Project"], namespace=d["Namespace"],
               llm_commit=answer.get("emerged_in", ""), actual_commit=actual.get(k, "")[:10])
    try:
        sha = revision(repo_dir, commit, row["llm_commit"])
    except ValueError:
        return {**row, "verdict": "no_commit"}

    parents = git(repo_dir, "rev-list", "--parents", "-n", "1", sha).split()[1:]
    now, before = at(sha), (at(parents[0]) if parents else set())
    shown = lambda found: "failed" if found is None else ("yes" if k in found else "no")
    row.update(present_at=shown(now), present_before=shown(before) if parents else "no parent")
    if now is None or before is None:
        row["verdict"] = "unverifiable"
    elif k not in now:
        row["verdict"] = "not_present"
    elif k in before:
        row["verdict"] = "already_present"
    else:
        row["verdict"] = "confirmed"
    if k in actual:
        row["distance"] = distance(repo_dir, sha, actual[k])
    return row


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
            actual = actual_commits(repo_dir, commit, {key(s["designite"]) for s in data["smells"]}, at)
            rows = [verify(s, repo_dir, commit, actual, at) for s in data["smells"]]
        finally:
            git(repo_dir, "worktree", "remove", "--force", str(worktree))

        with open(out / "verification.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(COLUMNS))
            w.writeheader()
            w.writerows(rows)
        confirmed = [r for r in rows if r["verdict"] == "confirmed"]
        print(f"    {len(confirmed)}/{len(rows)} confirmed, {sum(r['distance'] == 0 for r in confirmed)} exact "
              f"-> {out.relative_to(ROOT).as_posix()}/verification.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="*", help="owner/repo as in data/subjects.csv (default: all with explanations)")
    main(parser.parse_args().repos)
