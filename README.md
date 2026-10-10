# Architectural smell study

Selects new open-source C# projects from GitHub, clones a fixed version of each,
and runs Designite on them.

## Structure

```
scripts/
  screen.sh          1. search GitHub and measure candidates   -> data/screened.tsv
  clone_repos.sh     2. clone the repos that have a .sln        -> repos/, data/subjects.csv
  run_designite.sh   3. run Designite on every cloned repo      -> output/designite/
data/                screening results and data/subjects.csv (repo, url, tag, commit)
repos/               cloned repos (not committed; re-create with step 2)
tools/               third-party tools, e.g. tools/designite/ (not committed)
output/              analysis results
```

## Requirements

- Git, Git LFS, GitHub CLI (`gh auth login` once), .NET SDK
- Designite runs only on Windows: run step 3 in Git Bash on Windows

## Usage

Run from the project folder:

```bash
bash scripts/screen.sh         # settings (date, size, limit) at the top of the script
bash scripts/clone_repos.sh
bash scripts/run_designite.sh  # needs tools/designite/DesigniteConsole.dll
```

`clone_repos.sh` checks out each repo's latest tag; repos without tags stay on
their latest commit. `data/subjects.csv` records the tag and exact commit of
every cloned repo, so the same versions can be re-created later.
