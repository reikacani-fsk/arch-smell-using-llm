# Architectural smell study

Selects new open-source C# projects from GitHub, clones a fixed version of each,
and runs Designite on them.

## Structure

```
scripts/
  screen.sh          1. search GitHub and measure candidates    -> data/screened.tsv
  analyze.sh         2. clone the repos that have a .sln and     -> repos/, data/subjects.csv,
                        run Designite on them (all or chosen)       output/designite/
data/                screening results and data/subjects.csv (repo, url, tag, commit)
repos/               cloned repos (not committed; re-create with step 2)
tools/               third-party tools, e.g. tools/designite/ (not committed)
output/              analysis results
```

## Requirements

- Git, Git LFS, GitHub CLI (`gh auth login` once), .NET SDK
- Designite runs only on Windows: run step 2 in Git Bash on Windows

## Usage

Run from the project folder:

```bash
bash scripts/screen.sh    # settings (date, size, limit) at the top of the script
bash scripts/analyze.sh   # needs tools/designite/DesigniteConsole.dll
```

`analyze.sh` runs on every repo with solution type `sln` in `data/screened.tsv`.
To run only some, pass their names as in the `repo` column:

```bash
bash scripts/analyze.sh kangarooking/Ta chenjie2010/BlueSolution
```

`analyze.sh` checks out each repo's latest tag; repos without tags stay on
their latest commit. Repos already in `repos/` are not cloned again.
`data/subjects.csv` records the tag and exact commit of every analyzed repo, so
the same versions can be re-created later. Without arguments it is rewritten
from scratch; with arguments only the rows of the given repos are replaced.

Before Designite, each solution is restored with `dotnet restore`. Some repos
make Designite crash once restored; for those the restore output is removed and
Designite runs again without it (shown as `done (without restore)`).
