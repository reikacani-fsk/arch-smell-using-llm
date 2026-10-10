# LLM-assisted architectural smell detection

This is the thesis prototype. Claude judges each package of a Java or C# system for four architectural smells:
CyclicDependency, UnstableDependency, GodComponent and FeatureConcentration. Its answers are compared against
DesigniteJava (Java) or Designite (C#) and against manually validated labels.

| Config | What Claude sees for a package |
|---|---|
| C1 | Source code. A package over 60k characters is sent as a skeleton: imports, fields and signatures. |
| C2 | C1 + package-level dependency edges |
| C3 | C2 + the last 20 commits touching the package (messages, churn, co-changed packages) |
| C4 | C3 + RAG: related classes from neighbouring packages + notes from `knowledge/` |

| Project | Config | Language | Designite baseline |
|---|---|---|---|
| Commons IO 2.22.0 (pilot) | `config-commons-io.yaml` | Java | DesigniteJava, run locally |
| D_Parser (`projects/DParser2`) | `config-d-parser.yaml` | C# | DesigniteConsole, run on Windows (2019 `miningSmellData` result kept as an alternative) |

## Setup

You need Python 3.12+ and Git. Java projects also need JDK 21+ (DesigniteJava needs Java 22+). C# projects need nothing extra, except Designite itself, which runs only on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                   # 11 passed (without a JDK: 10 passed, 1 skipped)
```

Clone the project into `projects/` and check out the commit the config pins. The `release` value must match the code Designite analysed.

## Pipeline

Every command takes `--config <file>`. The examples set it once in `$c`.

```powershell
$c = "--config", "config-d-parser.yaml"
python -m smells.cli @c prepare        # dependency graph, package metrics, independent structural findings
```

**1. Run the Designite baseline.** The `designite:` section of the config holds the tool, the input and the output folder; `designite_csv` points at that folder (or at one CSV), and the architecture-smell CSV in it is found automatically. Column names are matched loosely.
```powershell
python -m smells.cli @c designite            # runs Designite (C#: Windows only)
python -m smells.cli @c designite --print    # only shows the command
```
The command it runs is the manual one: from the tool's folder, with absolute paths.
```powershell
cd tools\DesigniteConsole
dotnet .\DesigniteConsole.dll -i "<repo>\projects\DParser2\DParser2.sln" -o "<repo>\data\designite\D_Parser-windows"
```
For C#, check that the output covers the whole project: about 25 namespaces for D_Parser. If no CSV appears, read the newest file in `tools\DesigniteConsole\Logs\`. "Could not find any project to analyze" means the solution didn't load; installing Visual Studio Build Tools with ".NET desktop build tools" usually fixes it.

**2. Build the benchmark**
```powershell
python -m smells.cli @c crosscheck     # Designite vs the independent computation, per smell
python -m smells.cli @c benchmark      # writes data/<project>/benchmark.csv; never overwrites it without --force
```

**3. Label it.** In `benchmark.csv`, fill in `label` (1 = smell, 0 = none) and a short `rationale`. A second rater fills in `rater2_label` for about 25% of the rows. Then run `python -m smells.cli @c kappa`.

**4. Run Claude.** A C3/C4 prompt is roughly 10–20k input tokens, so check prices before a full run.
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python -m smells.cli @c index                                   # RAG index; downloads the embedding model once
python -m smells.cli @c prompt D_Parser.Dom --context C4         # print one prompt to inspect it
python -m smells.cli @c run --configs C1 --limit 3 --repeats 1   # small first run
python -m smells.cli @c run --configs C1 C2 C3 C4                # full run (3 repeats)
```
Add `--dry-run` to test the pipeline without calling the API. Every call (prompt, answer, tokens, errors) is stored in `data/<project>/runs.sqlite`.

**5. Evaluate.** Results are majority-voted over repeats.
```powershell
python -m smells.cli @c evaluate --reference label       # against your labels: the thesis result
python -m smells.cli @c evaluate --reference tool_flag   # against raw Designite
```

## Java vs C#

Set `language: csharp` in the config to analyse C#. The steps above stay the same. For C#:

- **Packages are namespaces.** A file belongs to the namespace of its first type. A `partial` type spread over several files counts once.
- **No compiler is needed.** `prepare` resolves dependencies from source (`smells/csharp.py`) and writes them to `deps.txt`. Java uses `javac` + `jdeps`.
- **The resolution is name-based**, not Roslyn, so cite it as a threat to validity. On D_Parser it found every namespace dependency that Designite reports. About 95% of its dependencies also appear in Designite; the rest are real references in the second file of partial classes.
- **History (C3)** follows each namespace's files, because C# folders need not match namespaces.
  C3/C4 need `project_root` to be a git clone that contains `release`. A plain copy of the sources
  (like `projects/DParser2`) only supports C1/C2, and `prompt`/`run` refuse C3/C4 instead of silently sending no history.
- `bin/`, `obj/` and `.vs/` are ignored when reading C# sources.

## Rules that keep the experiment valid

- Designite output, labels and `structural_findings.csv` never go into a prompt or the RAG index.
- `smells/prompts.py` stays fixed across C1–C4. Changing it means re-running everything. A test pins the Java prompt.
- `benchmark.csv` holds the manual labels: never regenerate it with `--force` after labelling has started.

## Layout

```
config-*.yaml       one per project: release, paths, smells, thresholds, model, context budget
smells/cli.py       all commands
  depgraph.py       Java graph (javac, jdeps), metrics, structural findings, C2 text
  csharp.py         C# parsing, skeletons, dependency graph
  code_context.py   package source / skeletons (C1)
  history_context.py  git history (C3)
  rag.py            Chroma index + retrieval (C4)
  prompts.py        FIXED system prompt, definitions, one-shot example, output schema
  llm.py            Claude client, dry-run client, SQLite run log
  runner.py         experiment loop
  benchmark.py, evaluate.py, designite.py
knowledge/          RAG notes (replace the starter text with citable sources)
tests/              pytest suite with small Java and C# fixture projects
```

**Not yet built:** the Batches API for full runs, McNemar / Cochran's Q tests, RQ2 explanations, RQ3 refactorings and multi-release evolution.
