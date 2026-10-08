# Context for Claude Code

Master thesis prototype: LLM-assisted architectural smell detection in Java and C# (`language:` in the config).
RQ1 = detection accuracy across context configs C1-C4; RQ2 = explanation quality; RQ3 = refactoring suggestions.
Baselines: DesigniteJava (Java) and Designite/DesigniteConsole (C#, Windows only). LLM: Claude via the Anthropic API.
Projects: `config-commons-io.yaml` (Java pilot), `config-d-parser.yaml` (C#). README.md has the full pipeline.

## Rules that protect the validity of the experiment
- Never put Designite output, benchmark labels or `structural_findings.csv` into any prompt or the RAG index.
- `smells/prompts.py` must stay identical across C1-C4; changing it means re-running all configs.
  The Java system prompt is pinned by a hash test; the only language-dependent text is `SUBJECT`.
- Never overwrite `data/*/benchmark.csv` (manual labels). `benchmark` requires --force for a reason.
- Every LLM call goes through `RunLog.record` so it is stored in runs.sqlite. Do not bypass it.
- Use `--dry-run` for pipeline changes; real API runs cost money.

## Commands
- Tests: `python -m pytest -q`
- CLI: `python -m smells.cli --config <config> <prepare|crosscheck|benchmark|kappa|index|prompt|run|evaluate>`

## Next steps (not yet implemented)
- Message Batches API for full runs; McNemar / Cochran's Q significance tests (statsmodels)
- RQ2: explanation generation for confirmed smells + automatic grounding check against graph.json
- RQ3: structured refactoring operations + virtual refactoring on the class-level graph
- Evolution: Designite multi-commit mode over several releases
