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
  explain.py         RQ2: explain how each smell emerged         -> output/explanations/
  verify.py          RQ2: check the emergence commits            -> output/verification/
  refactor.py        RQ3: refactor each smell and check it       -> output/refactoring/
prompts/             system prompts: smell definitions (arch_smells.md), RQ2 (explain_smell.md), RQ3 (refactor_smell.md)
data/                screening results and data/subjects.csv (repo, url, tag, commit)
repos/               cloned repos (not committed; re-create with step 2)
tools/               third-party tools, e.g. tools/designite/ (not committed)
output/              analysis results
```

## Requirements

- Git, Git LFS, GitHub CLI (`gh auth login` once), .NET SDK
- Designite runs only on Windows: run step 2 in Git Bash on Windows. Not in
  WSL: typing `bash` in a Windows command prompt may start WSL, which does not
  see the Windows `dotnet` (`dotnet: command not found`). Open the Git Bash
  window, or run `"C:\Program Files\Git\bin\bash.exe" scripts/analyze.sh`
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

## Explaining how smells emerged (RQ2)

```bash
python scripts/explain.py --dry-run zo1223/OpaiTV   # only write the first message of each session, no LLM calls
python scripts/explain.py zo1223/OpaiTV             # one agent session per project
```

For every smell Designite found, `explain.py` lets an LLM agent find out how
and when it emerged. It runs one session per C# project, covering all of that
project's smells. Designite reports Dense Structure for `<All projects
included>`, so that smell gets its own session. For each session:

1. Each smell's participating classes (from Designite) are matched by class
   name to the `.cs` files of that project that declare them.
2. The LLM gets Designite's smells (finding, participating classes and files)
   and the definitions of those smells from `prompts/arch_smells.md`, but no
   history. The system prompt is `prompts/explain_smell.md`.
3. The LLM explores the history itself with read-only tools: `git_log`,
   `git_show`, `read_file`, `list_files` and `grep`. They only reach the
   analyzed commit in `data/subjects.csv` and its ancestors. A tool result is
   cut off after 40,000 characters; files and diffs come in pages of 500
   lines. A session ends when the LLM calls `submit_explanations`, and fails
   after 60 steps.
4. For each smell the LLM answers with the commit the smell last emerged in
   (the oldest commit of the unbroken run back from the analyzed commit in which
   the smell is present: if it was removed and came back, the commit it came
   back in, as `verify.py` checks), how it built up (a timeline of commits) and
   why it is a problem.
5. Every commit the LLM cites is checked: `grounded` is false if it cites a
   commit that is not in the analyzed history. Commits that did not change the
   smell's files are allowed (a smell can emerge through other files) and are
   listed in `other_commits`. A smell the LLM did not answer is recorded as an
   error.

Results go to `output/explanations/<owner>_<repo>/`: `explanations.json` (per
smell: finding, files, commits that changed them, answer and grounding check;
per session: every step with its text and tool calls, and token usage),
`explanations.md` (readable, e.g. for developers to rate) and
`prompts/<project>.md` (the first message of each session).

### Testbed with known answers

[rkacani/bookstore](https://github.com/rkacani/bookstore) is a small C# repo in
which each smell emerges in a known commit for a known reason. It includes a
smell that is removed and comes back, and smells that emerge through files
Designite does not list. It goes through the pipeline like any other repo (it
is in `data/screened.tsv`). `testbed/ground_truth.json` records the answers, and
`testbed/score.py` compares the LLM's explanations with them. See
[testbed/README.md](testbed/README.md).

### Checking the emergence commits with Designite

```bash
python scripts/verify.py                  # all repos with explanations (on Windows, like analyze.sh)
python scripts/verify.py zo1223/OpaiTV    # only the given repos
```

`verify.py` checks the commit in which the LLM says each smell last emerged:
the oldest commit of the unbroken run, back from the analyzed commit, in which
Designite finds the smell (an earlier appearance that was fixed does not count).
For each smell it runs Designite on the analyzed commit and goes back through the
commits that change C# code, down to the LLM's commit and then its parent. It
stops at the first commit without the smell, so older commits are never analyzed.
Example with commits c1 ... c8 (c8 analyzed):

| LLM says | Designite finds the smell at | verdict     | analyzed           |
|----------|------------------------------|-------------|--------------------|
| c5       | c5 ... c8, not at c4         | `confirmed` | c8, c7, c6, c5, c4 |
| c3       | c7, c8, not at c6            | `too_early` | c8, c7, c6         |
| c6       | c3 ... c8                    | `too_late`  | c8, c7, c6, c5     |

A smell counts as the same if smell, project and namespace match (for Cyclic
Dependency and Scattered Functionality also the components Designite lists);
classes and descriptions are not compared, since they change as the code grows.

Designite runs in a temporary git worktree, so `repos/` stays at the analyzed
commit. Its results are cached per commit, in
`output/verification/<owner>_<repo>/designite/<commit>/`, and shared by all
smells. Commits Designite fails on are skipped, except the LLM's commit and its
parent. The result is `output/verification/<owner>_<repo>/verification.csv`, one
row per smell:

| column           | meaning                                                                                                   |
|------------------|-----------------------------------------------------------------------------------------------------------|
| `description`    | Designite's description at the analyzed commit (for Cyclic Dependency and Scattered Functionality its components tell apart the smells of one namespace) |
| `llm_commit`     | commit the LLM says the smell emerged in                                                                  |
| `present_at`     | smell found at `llm_commit`: `yes`, `no`, or empty if not analyzed (the walk stopped at a later commit)   |
| `present_before` | smell found at its parent: `yes`, `no`, `no parent`, or empty if not analyzed                             |
| `verdict`        | `confirmed`, `too_early`, `too_late`, `not_reproduced` (Designite does not find the smell at the analyzed commit in this run), `unverifiable` (Designite failed on `llm_commit` or its parent) or `no_commit` (no answer, or a commit outside the analyzed history) |
| `actual_commit`  | commit the smell last emerged in, if known: `llm_commit` when `confirmed`, the oldest commit of the unbroken run when `too_early`; empty otherwise |

## Refactoring the smells (RQ3)

```bash
python scripts/refactor.py --dry-run zo1223/OpaiTV          # only write the first message of the session, no LLM calls
python scripts/refactor.py zo1223/OpaiTV                    # Windows, like verify.py: one agent session for all smells
python scripts/refactor.py --with-explanation zo1223/OpaiTV # the same, with how each smell emerged (RQ2)
```

`refactor.py` lets an LLM agent refactor the code to remove all smells
Designite found in a repo, in one session, and then checks the result once:

1. The agent works in a temporary git worktree at the analyzed commit. It gets
   every smell (Designite's finding, participating classes and their files),
   the smells' definitions and what a component and a dependency are (from
   `prompts/arch_smells.md`). With `--with-explanation` it also gets the RQ2
   explanation of how each smell emerged (`output/explanations/`), so the two
   variants show whether that context helps. The system prompt is
   `prompts/refactor_smell.md`: goals, method (find the causes, plan across the
   smells since they often share a cause, apply and build step by step, check),
   a catalog of refactorings and rules (keep behaviour and tests, remove
   dependencies instead of hiding them).
2. The agent reads and edits the code with `list_files`, `read_file`, `grep`,
   `edit_file`, `write_file` and `delete_file`, and can call `build` and, if the
   solution has a test project, `run_tests`. It cannot run Designite. It ends
   with `submit_refactoring`: a summary, and for every smell the refactorings
   applied (from the catalog), the steps and a rationale. Each step is printed
   while it runs. A session fails after 200 steps. A model turn that fails
   because the connection drops or the API is overloaded is retried 5 times
   (after 15 s, 30 s, ... 240 s).
3. Its changes are committed in the worktree, saved as a patch, and checked:

| # | column          | check                                                                                     |
|---|-----------------|-------------------------------------------------------------------------------------------|
| 1 | `builds`        | `dotnet build` of the solution succeeds (one value for the whole refactoring)              |
| 2 | `tests_pass`    | `dotnet test` succeeds; `no_tests` if the solution has no test project, `failing_before` if the tests already fail at the analyzed commit |
| 3 | `smell_removed` | per smell: Designite no longer finds it (the same smell as in `verify.py`)                 |
| 4 | new smells      | each smell Designite finds after the refactoring but not at the analyzed commit gets its own row, with verdict `new_smell` |

Repos that do not build or that Designite fails on at the analyzed commit are
skipped. Smells Designite does not find at the analyzed commit in this run are
not given to the LLM (`not_reproduced`). For the other smells the `verdict` is
the first failed check: `broken_build`, `tests_fail`, `unverifiable` (Designite
failed on the refactored code), `not_fixed`, otherwise `fixed`; `no_answer` if
the session failed or the LLM did not answer the smell. Since all smells are
refactored together, a broken build or failing tests count for every smell,
and a new smell cannot be traced to the refactoring of one smell.

Results go to `output/refactoring/<variant>/<owner>_<repo>/` (variant `code`, or
`explanation`): `refactoring.csv` (one row per smell and per new smell: `id`,
smell, project, namespace, description, `refactoring_type`, the checks and
`verdict`), `refactorings.json` (the summary; per smell its finding, answer and
checks; the new smells; every step of the session and token usage),
`refactorings.md` (readable), `refactoring.patch` (the code changes),
`prompt.md` (the first message) and `designite/` (Designite's results per
commit, cached).

For the testbed, `testbed/ground_truth.json` records for each smell the
refactorings that remove it and the intended fix. `testbed/score.py` compares
them with the LLM's refactorings in `output/testbed/refactoring_score.csv`.
