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
python scripts/llm_analyze.py                    # all repos with Designite results
python scripts/llm_analyze.py zo1223/OpaiTV      # only the given repos
python scripts/compare.py
```

`llm_analyze.py` uses the repos already cloned in `repos/` by step 2. It gives the
LLM the same input as Designite: every `.cs` file (without `bin/` and `obj/`) of
the C# projects in the `.sln` closest to the repo root. The system prompt
(`prompts/arch_smells.md`) defines the six smells: Cyclic Dependency, Unstable
Dependency, God Component, Feature Concentration, Scattered Functionality and
Dense Structure. The model and effort are set at the top of the script. The
LLM answers in a fixed JSON format, which is saved as
`output/llm/<owner>_<repo>/ArchSmells.csv`. That file has the same columns as
Designite's `*_ArchSmells.csv`: smell, project, namespace, description and
participating classes. The model, token usage and raw answer are saved in
`response.json` next to it.

`compare.py` reads both results for every repo that has them and writes:

- `output/comparison/counts.csv`: for each repo, project and smell, the number
  of instances found by Designite and by the LLM, their difference
  (llm - designite), and how many namespaces both flagged for that smell
- `output/comparison/instances.csv`: every instance found by either tool, one
  row each, with a `tool` column

Designite's Ambiguous Interface smell is not part of the comparison.
