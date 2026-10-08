"""Runs the RQ1 experiment: every benchmark package x context config x repeat."""
import uuid

import pandas as pd

from . import prompts
from .code_context import index_sources, package_code_context, skeleton
from .depgraph import graph_context, load_graph
from .history_context import package_history

CONFIGS = ["C1", "C2", "C3", "C4"]   # cumulative: code, +graph, +history, +RAG


class ContextBuilder:
    def __init__(self, cfg):
        self.cfg = cfg
        self.index = index_sources(cfg.source_dirs, cfg.language)
        self.pkg_g, _ = load_graph(cfg.data_dir / "graph.json")
        self._retriever = None

    @property
    def retriever(self):
        if self._retriever is None:
            from .rag import Retriever
            self._retriever = Retriever(self.cfg.data_dir / "chroma", self.cfg["context"]["embedding_model"])
        return self._retriever

    def sections(self, package: str, config: str) -> list[str]:
        level = CONFIGS.index(config)
        c = self.cfg["context"]
        out = [package_code_context(package, self.index, c["max_source_chars"])]
        if level >= 1:
            out.append(graph_context(package, self.pkg_g))
        if level >= 2:
            out.append(package_history(self.cfg.project_root, self.cfg.source_dirs, package,
                                       self.cfg["release"], c["history_commits"],
                                       self.index if self.cfg.language == "csharp" else None))
        if level >= 3:
            neigh = []
            if package in self.pkg_g:
                neigh = sorted(set(self.pkg_g.successors(package)) | set(self.pkg_g.predecessors(package)))
            query = "\n".join(skeleton(f.text, f.language) for f in self.index.get(package, []))
            out.append(self.retriever.context(package, query, neigh, c["rag_top_k"]))
        return out


def run_experiment(cfg, client, log, configs, packages=None, limit=None, repeats=None, progress=print):
    bench = pd.read_csv(cfg.data_dir / "benchmark.csv")
    pkgs = packages or sorted(bench.package.unique())
    if limit:
        pkgs = pkgs[:limit]
    smells = cfg["smells"]
    system = prompts.system_prompt(smells, cfg.language)
    schema = prompts.output_schema(smells)
    builder = ContextBuilder(cfg)
    run_id = uuid.uuid4().hex[:8]
    repeats = repeats or cfg["llm"].get("repeats", 1)
    failures = 0
    for r in range(repeats):
        for config in configs:
            for i, pkg in enumerate(pkgs, 1):
                user = prompts.user_prompt(pkg, builder.sections(pkg, config))
                meta = {"run_id": run_id, "project": cfg["project_name"], "release": cfg["release"],
                        "package": pkg, "config": config, "model": client.model, "repeat": r}
                parsed, err = log.record(meta, system, user, prompts.prompt_hash(system, user),
                                         lambda: client.complete(system, user, schema))
                failures += parsed is None
                progress(f"[{run_id}] rep {r} {config} {i}/{len(pkgs)} {pkg}"
                         + (f"  ERROR {err}" if err else ""))
    return run_id, failures
