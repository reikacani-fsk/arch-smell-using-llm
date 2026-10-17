# Architectural smell study

Selects new open-source C# projects from GitHub, clones a fixed version of each,
detects their architectural smells with Designite and with an LLM, and compares the two.

## Structure

```
scripts/
  screen.sh          1. search GitHub and measure candidates    -> data/screened.tsv
  analyze.sh         2. clone the repos that have a .sln and     -> repos/, data/subjects.csv,
                        run Designite on them (all or chosen)       output/designite/
  llm_analyze.py     3. ask the LLM for the same smells          -> output/llm/
  compare.py         4. put both results side by side            -> output/comparison/
prompts/             system prompt with the smell definitions given to the LLM
data/                screening results and data/subjects.csv (repo, url, tag, commit)
repos/               cloned repos (not committed; re-create with step 2)
tools/               third-party tools, e.g. tools/designite/ (not committed)
output/              analysis results
```

## Requirements

- Git, Git LFS, GitHub CLI (`gh auth login` once), .NET SDK
- Designite runs only on Windows: run step 2 in Git Bash on Windows
- Steps 3-4: Python 3 and `pip install -r requirements.txt`
- Step 3: an Anthropic API key. Copy `.env-example` to `.env` and fill in
  `ANTHROPIC_API_KEY` (`.env` is not committed)

## Usage

Run from the project folder in Git Bash on Windows:

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

## LLM analysis and comparison

```bash
python scripts/llm_analyze.py                              # 0-shot, all repos with Designite results
python scripts/llm_analyze.py --shots 1 zo1223/OpaiTV      # 1-shot, only the given repos
python scripts/llm_analyze.py --shots 2 zo1223/OpaiTV      # 2-shot: examples 1 and 2
python scripts/llm_analyze.py --history kangarooking/Ta    # 0-shot + git history, only the given repos
python scripts/compare.py
```

`llm_analyze.py` uses the repos already cloned in `repos/` by step 2. It gives the
LLM the same input as Designite: every `.cs` file (without `bin/` and `obj/`) of
the C# projects in the `.sln` closest to the repo root. The system prompt
(`prompts/arch_smells.md`) defines the seven architecture smells Designite
detects: Cyclic Dependency, Unstable Dependency, Ambiguous Interface, God
Component, Feature Concentration, Scattered Functionality and Dense Structure.
The model and effort are set at the top of the script.

`--shots N` (default 0) shows the LLM N worked examples before the repo. Each
example is one earlier exchange: its code as the user turn and its correct
answer as the reply. Examples are in `prompts/examples/<n>/`: one folder per
C# project with its `.cs` files, plus `answer.json` with the expected smells.
Example 1 has four short projects that together contain every smell:

| Project      | Smells                                                         |
|--------------|----------------------------------------------------------------|
| `Shop.Core`  | Cyclic Dependency, Unstable Dependency, Feature Concentration  |
| `Clinic.App` | Scattered Functionality, Ambiguous Interface                   |
| `Geometry`   | God Component                                                  |
| `Warehouse`  | Dense Structure                                                |

Example 2 is a small library system with three projects. It covers cases that
example 1 does not show:

| Project           | Smells                                                                                                                                          |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| `Library.Desktop` | two overlapping Cyclic Dependencies (a 2-cycle and a 3-cycle), Unstable Dependency, Feature Concentration in a namespace of pages that do not use each other |
| `Library.Core`    | Scattered Functionality (a cache implemented twice); `Library.Core.Loans` has several concerns but its classes are connected, so it has no Feature Concentration |
| `Library.Tests`   | God Component and Feature Concentration in a test project (32 classes in 10 independent groups)                                                |

To allow more shots, add `prompts/examples/3/` with the same layout.

`--history` adds a summary of the repo's git history to the prompt, after the
code (built by `scripts/history.py`). It is a separate context variant that is
compared with the 0-shot code-only baseline, so it cannot be combined with
`--shots`, and the repos must be given. The summary only uses commits up to the
analyzed commit in `data/subjects.csv`, and counts only commits (without merges)
that change the `.cs` files the LLM sees. Changes are grouped by component
(`project/namespace`, the unit Designite reports smells for):

- how many commits changed each component and each file (churn)
- which components changed in the same commits (co-change). Commits with more
  than 30 files, such as an initial import, are left out of this list.

Repos with fewer than 10 such commits are skipped (`MIN_COMMITS` in
`llm_analyze.py`), since they have too little history. Results go to
`output/llm/history/<owner>_<repo>/`, with the summary the LLM got saved as
`history.md`.

The LLM answers in a fixed JSON format, which is saved as
`output/llm/<N>shot/<owner>_<repo>/ArchSmells.csv`. That file has the same
columns as Designite's `*_ArchSmells.csv`: smell, project, namespace,
description and participating classes. The model, number of shots, token usage
and raw answer are saved in `response.json` next to it.

`compare.py` reads Designite and every prompt variant (`0shot`, `1shot`, ...,
`history`) for each repo and writes:

- `output/comparison/counts.csv`: for each repo, project and smell, the number
  of instances found by Designite. For each variant it adds the number found by
  the LLM, the difference (llm - designite), and how many namespaces both
  flagged for that smell. A variant's cells are empty if it has no result for
  the repo.
- `output/comparison/instances.csv`: every instance found by Designite or a
  variant, one row each, with a `tool` column (`designite`, `0shot`, `1shot`, ...)
