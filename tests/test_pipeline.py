import hashlib
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from smells import cli, prompts
from smells.code_context import index_sources, package_code_context, package_size, skeleton
from smells.config import Config
from smells.csharp import class_graph
from smells.depgraph import instability, package_graph, parse_jdeps
from smells.designite import load_architecture_smells
from smells.llm import ClaudeClient

FIX = Path(__file__).parent / "fixtures"
HAS_JDK = (shutil.which("jdeps") and shutil.which("javac")      # macOS has stubs without a JDK behind them
           and subprocess.run(["javac", "-version"], capture_output=True).returncode == 0)


def _make_workspace(tmp_path, repo_name, config, designite_csv, tweak):
    """Copy of a fixture project as a git repo, plus config and Designite CSV.
    Second commit touches the `tweak` files together (for C3 history and co-change)."""
    shutil.copytree(FIX / repo_name, tmp_path / repo_name)
    shutil.copy(FIX / config, tmp_path / "config.yaml")
    shutil.copy(FIX / designite_csv, tmp_path)
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "notes.md").write_text(
        "# Notes\n## Breaking cycles\nIntroduce an interface in the lower-level package.\n"
        "## Splitting packages\nMove unrelated classes to cohesive packages.\n", encoding="utf-8")
    repo = tmp_path / repo_name
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-qm", "initial import"], check=True)
    for rel in tweak:
        f = repo / rel
        f.write_text(f.read_text() + "\n// tweak\n")
    subprocess.run(git + ["commit", "-qam", "change alpha and beta together"], check=True)
    return tmp_path


@pytest.fixture
def workspace(tmp_path):
    return _make_workspace(tmp_path, "minirepo", "config.yaml", "designite_ArchitectureSmells.csv",
                           ["src/main/java/com/ex/a/Alpha.java", "src/main/java/com/ex/b/Beta.java"])


@pytest.fixture
def cs_workspace(tmp_path):
    return _make_workspace(tmp_path, "minirepo-cs", "config-cs.yaml", "designite_cs_ArchSmells.csv",
                           ["src/Core/Alpha.cs", "src/Beta/Beta.Compute.cs"])


def test_designite_parser():
    df = load_architecture_smells(FIX / "designite_ArchitectureSmells.csv")
    assert set(df.smell) == {"CyclicDependency", "FeatureConcentration"}
    assert len(df) == 3   # duplicate row removed


def test_parse_jdeps_text():
    text = ("classes -> java.base\n"
            "   com.ex.a.Alpha     -> com.ex.b.Beta      classes\n"
            "   com.ex.a.Alpha     -> java.lang.Object   java.base\n"
            "   com.ex.b.Beta$1    -> com.ex.a.Alpha     classes\n"
            "   com.ex.c.Gamma     -> com.ex.a.Alpha     classes\n")
    g = parse_jdeps(text, "com.ex")
    assert ("com.ex.b.Beta", "com.ex.a.Alpha") in g.edges      # nested class folded into outer
    pg = package_graph(g)
    assert set(pg.edges) == {("com.ex.a", "com.ex.b"), ("com.ex.b", "com.ex.a"), ("com.ex.c", "com.ex.a")}
    inst = instability(g)
    assert inst["com.ex.c"]["I"] == 1.0 and inst["com.ex.a"]["Ca"] == 2


def test_skeleton_drops_bodies():
    text = (FIX / "minirepo/src/main/java/com/ex/d/Delta.java").read_text()
    sk = skeleton(text)
    assert "public String name(int i);" in sk
    assert "System.out" not in sk and "FAST," in sk and "LIMIT = 3" in sk


def test_code_context_switches_to_skeleton():
    idx = index_sources([FIX / "minirepo/src/main/java"])
    assert set(idx) == {"com.ex.a", "com.ex.b", "com.ex.c", "com.ex.d"}
    assert "Full source" in package_code_context("com.ex.c", idx, 10_000)
    small = package_code_context("com.ex.c", idx, 50)
    assert "skeletons" in small and "long body" not in small


def test_schema_and_prompt():
    smells = ["CyclicDependency", "GodComponent"]
    s = prompts.output_schema(smells)
    assert s["properties"]["smells"]["items"]["properties"]["smell"]["enum"] == smells
    assert "GodComponent" in prompts.system_prompt(smells)


def test_claude_client_request_shape():
    """Checks the exact API request without network: structured outputs + cached system prompt."""
    captured = {}

    class FakeMessages:
        def create(self, **kw):
            captured.update(kw)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"package":"p","smells":[]}')],
                                   usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                                                         cache_read_input_tokens=0, cache_creation_input_tokens=10))

    c = ClaudeClient("claude-sonnet-5-5", 100, 0, client=SimpleNamespace(messages=FakeMessages()))
    text, usage = c.complete("SYS", "USER", {"type": "object"})
    assert json.loads(text)["package"] == "p" and usage["input_tokens"] == 10
    assert captured["output_config"]["format"]["type"] == "json_schema"
    assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert captured["temperature"] == 0


def test_csharp_skeleton_drops_bodies():
    sk = skeleton((FIX / "minirepo-cs/src/Misc/Delta.cs").read_text(), "csharp")
    assert "public string Name(int i);" in sk and "public int Size { get; private set; }" in sk
    assert "Console" not in sk and "Fast," in sk and "Limit = 3" in sk
    assert "private int dbg;" in sk                                   # member inside #if kept
    assert "namespace Ex.A" in skeleton((FIX / "minirepo-cs/src/Core/Alpha.cs").read_text(), "csharp")


def test_csharp_index_and_class_graph():
    idx = index_sources([FIX / "minirepo-cs/src"], "csharp")
    assert set(idx) == {"Ex.A", "Ex.B", "Ex.C", "Ex.D"}             # namespaces, not folders
    assert package_size(idx)["Ex.B"][1] == 1                          # partial class counted once
    g = class_graph([FIX / "minirepo-cs/src"], "Ex")
    # Alpha->Beta via using, Beta->Alpha via alias, Gamma->Alpha via qualified name;
    # Gamma's property named "Beta" is not a reference to Ex.B.Beta
    assert set(g.edges) == {("Ex.A.Alpha", "Ex.B.Beta"), ("Ex.B.Beta", "Ex.A.Alpha"),
                            ("Ex.C.Gamma", "Ex.A.Alpha")}
    assert "Ex.D.Delta" in g and "Ex.D.Delta.Inner" not in g          # nested type folded


def test_java_system_prompt_unchanged():
    """Adding C# must not change the Java prompt: runs already logged would no longer be comparable."""
    s = prompts.system_prompt(["CyclicDependency", "UnstableDependency", "GodComponent", "FeatureConcentration"])
    assert hashlib.sha256(s.encode()).hexdigest() == \
        "8fb28ff319f2da1137e06c99d4b32e87442bfa409ead5c0f6b99f0ba5886149a"
    assert "a C# system" in prompts.system_prompt(["GodComponent"], "csharp")


@pytest.mark.skipif(not HAS_JDK, reason="needs javac + jdeps")
def test_end_to_end_dry_run(workspace, capsys):
    _end_to_end(workspace, capsys, "com.ex.a", "com.ex.b", ["--javac"])


def test_end_to_end_dry_run_csharp(cs_workspace, capsys):
    _end_to_end(cs_workspace, capsys, "Ex.A", "Ex.B", [])


def _end_to_end(workspace, capsys, pkg_a, pkg_b, prepare_args):
    cfgp = str(workspace / "config.yaml")
    cli.main(["--config", cfgp, "prepare"] + prepare_args)
    cfg = Config(cfgp)
    sf = pd.read_csv(cfg.data_dir / "structural_findings.csv")
    cyc = set(sf[sf.smell == "CyclicDependency"].package)
    assert cyc == {pkg_a, pkg_b}

    cli.main(["--config", cfgp, "crosscheck"])
    cli.main(["--config", cfgp, "benchmark"])
    bench = pd.read_csv(cfg.data_dir / "benchmark.csv")
    assert bench.tool_flag.sum() == 3 and bench.package.nunique() == 4
    with pytest.raises(SystemExit):           # protects manual labels
        cli.main(["--config", cfgp, "benchmark"])

    cli.main(["--config", cfgp, "index"])
    cli.main(["--config", cfgp, "prompt", pkg_a, "--context", "C4"])
    out = capsys.readouterr().out
    assert ("a C# system" in out) == (cfg.language == "csharp")
    assert f"{pkg_a} -> {pkg_b}" in out                       # C2 graph
    assert "change alpha and beta together" in out            # C3 history
    assert f"{pkg_b} (" in out                                # C3 co-change
    assert "Related class from a neighbouring package" in out # C4 RAG
    assert "Designite" not in out.split("=== USER ===")[1]    # no tool leakage

    cli.main(["--config", cfgp, "run", "--dry-run", "--configs", "C1", "C2", "C3", "C4"])
    con = sqlite3.connect(cfg.data_dir / "runs.sqlite")
    assert con.execute("SELECT COUNT(*) FROM calls WHERE parsed_ok=1").fetchone()[0] == 4 * 4 * 2
    assert con.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 4 * 4 * 2 * 4

    cli.main(["--config", cfgp, "evaluate", "--reference", "tool_flag"])
    res = pd.read_csv(cfg.data_dir / "results_tool_flag.csv")
    assert set(res.config) == {"C1", "C2", "C3", "C4"}
    assert (res[res.positives > 0].recall == 0).all()        # dry-run predicts "no smell"

    bench.loc[:3, "label"] = [1, 0, 0, 0]
    bench.loc[:3, "rater2_label"] = [1, 0, 1, 0]
    bench.to_csv(cfg.data_dir / "benchmark.csv", index=False)
    cli.main(["--config", cfgp, "kappa"])
    assert "Cohen's kappa = 0.500" in capsys.readouterr().out
