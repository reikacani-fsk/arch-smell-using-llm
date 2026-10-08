"""Command-line entry point:  python -m smells.cli --config config.yaml <command> [options]

  prepare      compile project (if needed), run jdeps (C#: resolve from source), build graph + findings
  crosscheck   compare Designite with the independent structural computation
  benchmark    create data/<project>/benchmark.csv (never overwrites manual labels unless --force)
  kappa        inter-rater agreement on the manually labelled rows
  index        build the RAG index (needed for C4)
  prompt       print the exact prompt for one package + config (inspect / estimate size)
  run          run the LLM experiment
  evaluate     precision / recall / F1 per run, config, smell
"""
import argparse
import sys

import pandas as pd

from .config import Config


def cmd_prepare(cfg, a):
    from .code_context import index_sources, package_size
    from .depgraph import (compile_project, instability, package_graph, parse_jdeps, run_jdeps,
                           save_graph, structural_findings)
    if cfg.language == "csharp":                       # no compiler/jdeps: graph resolved from source
        from .csharp import class_graph, write_edges
        class_g = class_graph(cfg.source_dirs, cfg["package_prefix"])
        write_edges(class_g, cfg.data_dir / "deps.txt")
    else:
        if a.compile or not cfg.classes_dir.exists():
            print(f"Compiling {cfg.project_root} ...")
            compile_project(cfg.project_root, cfg.source_dirs, cfg.classes_dir, use_maven=not a.javac)
        txt = run_jdeps(cfg.classes_dir, cfg.data_dir / "jdeps.txt")
        class_g = parse_jdeps(txt.read_text(encoding="utf-8"), cfg["package_prefix"])
    pkg_g = package_graph(class_g)
    inst = instability(class_g)
    sizes = {p: s for p, s in package_size(index_sources(cfg.source_dirs, cfg.language)).items()
             if p.startswith(cfg["package_prefix"])}
    for p in sizes:
        pkg_g.add_node(p)
        inst.setdefault(p, {"Ca": 0, "Ce": 0, "I": 0.0})
    save_graph(pkg_g, inst, cfg.data_dir / "graph.json")
    sf = structural_findings(pkg_g, inst, sizes, cfg["thresholds"])
    sf.to_csv(cfg.data_dir / "structural_findings.csv", index=False)
    pd.DataFrame([{"package": p, "loc": l, "types": t, **inst[p]} for p, (l, t) in sorted(sizes.items())]) \
        .to_csv(cfg.data_dir / "package_metrics.csv", index=False)
    print(f"{class_g.number_of_nodes()} classes, {pkg_g.number_of_nodes()} packages, "
          f"{pkg_g.number_of_edges()} package edges")
    print(sf.groupby("smell").size().to_string() if len(sf) else "No structural findings.")


def _tool_df(cfg, source):
    if source == "structural":
        df = pd.read_csv(cfg.data_dir / "structural_findings.csv").rename(columns={"evidence": "cause"})
        print("WARNING: using structural findings as tool reference (pilot mode, no Designite).")
        return df
    from .designite import load_architecture_smells
    return load_architecture_smells(cfg.path("designite_csv"))


def _packages(cfg):
    import json
    return json.loads((cfg.data_dir / "graph.json").read_text(encoding="utf-8"))["nodes"]


def cmd_crosscheck(cfg, a):
    from .benchmark import crosscheck
    sf = pd.read_csv(cfg.data_dir / "structural_findings.csv")
    out = crosscheck(_tool_df(cfg, a.source), sf, _packages(cfg), cfg["smells"])
    print(out.to_string(index=False))
    out.to_csv(cfg.data_dir / "crosscheck.csv", index=False)


def cmd_benchmark(cfg, a):
    from .benchmark import build_benchmark
    path = cfg.data_dir / "benchmark.csv"
    if path.exists() and not a.force:
        sys.exit(f"{path} exists (may contain manual labels). Use --force to overwrite.")
    sf = pd.read_csv(cfg.data_dir / "structural_findings.csv")
    b = cfg.get("benchmark", {})
    bench = build_benchmark(cfg["project_name"], cfg["release"], _tool_df(cfg, a.source), sf,
                            _packages(cfg), cfg["smells"], b.get("clean_ratio", 1.0), b.get("seed", 42))
    bench.to_csv(path, index=False)
    print(f"Wrote {path}: {bench.package.nunique()} packages, {len(bench)} (package, smell) rows, "
          f"{int(bench.tool_flag.sum())} tool-flagged.")


def cmd_kappa(cfg, a):
    from .benchmark import kappa
    k, n = kappa(pd.read_csv(cfg.data_dir / "benchmark.csv"))
    print("No rows with both label and rater2_label yet." if k is None else f"Cohen's kappa = {k:.3f} on {n} rows")


def cmd_index(cfg, a):
    from .code_context import index_sources
    from .rag import build_index
    n_code, n_kb = build_index(index_sources(cfg.source_dirs, cfg.language), cfg.base / "knowledge",
                               cfg.data_dir / "chroma", cfg["context"]["embedding_model"])
    print(f"Indexed {n_code} code chunks and {n_kb} knowledge chunks.")


def cmd_prompt(cfg, a):
    from . import prompts
    from .runner import ContextBuilder
    user = prompts.user_prompt(a.package, ContextBuilder(cfg).sections(a.package, a.context))
    system = prompts.system_prompt(cfg["smells"], cfg.language)
    print("=== SYSTEM ===\n" + system + "\n=== USER ===\n" + user)
    print(f"\n~{(len(system) + len(user)) // 4} tokens (rough estimate: chars / 4)", file=sys.stderr)


def cmd_run(cfg, a):
    from .llm import ClaudeClient, DryRunClient, RunLog
    from .runner import run_experiment
    llm = cfg["llm"]
    client = DryRunClient() if a.dry_run else ClaudeClient(a.model or llm["model"], llm["max_tokens"],
                                                           llm.get("temperature"))
    log = RunLog(cfg.data_dir / "runs.sqlite")
    run_id, failures = run_experiment(cfg, client, log, a.configs, packages=a.packages, limit=a.limit,
                                      repeats=a.repeats)
    print(f"Done. run_id={run_id}, failed calls={failures}")


def cmd_evaluate(cfg, a):
    from .evaluate import evaluate, load_predictions
    res = evaluate(pd.read_csv(cfg.data_dir / "benchmark.csv"),
                   load_predictions(cfg.data_dir / "runs.sqlite", a.run_id), a.reference)
    print(res.to_string(index=False))
    res.to_csv(cfg.data_dir / f"results_{a.reference}.csv", index=False)


def main(argv=None):
    p = argparse.ArgumentParser(prog="smells")
    p.add_argument("--config", default="config.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("prepare")
    s.add_argument("--compile", action="store_true", help="force recompilation")
    s.add_argument("--javac", action="store_true", help="use plain javac instead of Maven")
    for name in ("crosscheck", "benchmark"):
        s = sub.add_parser(name)
        s.add_argument("--source", choices=["designite", "structural"], default="designite")
        if name == "benchmark":
            s.add_argument("--force", action="store_true")
    sub.add_parser("kappa")
    sub.add_parser("index")
    s = sub.add_parser("prompt")
    s.add_argument("package")
    s.add_argument("--context", default="C1", choices=["C1", "C2", "C3", "C4"])
    s = sub.add_parser("run")
    s.add_argument("--configs", nargs="+", default=["C1"], choices=["C1", "C2", "C3", "C4"])
    s.add_argument("--packages", nargs="+")
    s.add_argument("--limit", type=int)
    s.add_argument("--repeats", type=int)
    s.add_argument("--model")
    s.add_argument("--dry-run", action="store_true", help="no API calls; tests the pipeline")
    s = sub.add_parser("evaluate")
    s.add_argument("--reference", default="label", choices=["label", "tool_flag", "structural_flag"])
    s.add_argument("--run-id")
    a = p.parse_args(argv)
    cfg = Config(a.config)
    globals()[f"cmd_{a.cmd}"](cfg, a)


if __name__ == "__main__":
    main()
