"""Dependency graph from jdeps + independent structural smell computation (cross-check for Designite)."""
import json
import shutil
import subprocess
from pathlib import Path

import networkx as nx
import pandas as pd


def _tool(name):
    exe = shutil.which(name)
    if not exe:
        raise RuntimeError(f"'{name}' not found on PATH (install a JDK and/or Maven)")
    return exe


def compile_project(project_root: Path, source_dirs, classes_dir: Path, use_maven=True):
    """Compile with Maven if possible, otherwise plain javac (works for projects without external deps)."""
    if use_maven and (project_root / "pom.xml").exists() and shutil.which("mvn"):
        subprocess.run([_tool("mvn"), "-q", "-DskipTests", "-Drat.skip", "-Dcheckstyle.skip",
                        "-Dspotbugs.skip", "-Dpmd.skip", "-Djacoco.skip", "-Danimal.sniffer.skip",
                        "compile"], cwd=project_root, check=True)
        return
    classes_dir.mkdir(parents=True, exist_ok=True)
    files = [str(p) for d in source_dirs for p in Path(d).rglob("*.java")
             if p.name != "module-info.java"]
    argfile = classes_dir.parent / "javac-sources.txt"
    argfile.write_text("\n".join(f'"{f}"'.replace("\\", "/") for f in files), encoding="utf-8")
    subprocess.run([_tool("javac"), "-nowarn", "-proc:none", "-encoding", "UTF-8", "-d",
                    str(classes_dir), f"@{argfile}"], check=True)


def run_jdeps(classes_dir: Path, out_txt: Path) -> Path:
    res = subprocess.run([_tool("jdeps"), "-verbose:class", "-filter:none", str(classes_dir)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    out_txt.write_text(res.stdout, encoding="utf-8")
    return out_txt


def outer_class(name: str) -> str:
    return name.split("$", 1)[0]


def package_of(cls: str) -> str:
    return cls.rsplit(".", 1)[0] if "." in cls else ""


def parse_jdeps(text: str, prefix: str) -> nx.DiGraph:
    """Class-level graph (nested classes folded into their outer class), project classes only."""
    g = nx.DiGraph()
    for line in text.splitlines():
        if not line.startswith((" ", "\t")) or "->" not in line:
            continue
        parts = line.split()
        if len(parts) < 3 or parts[1] != "->":
            continue
        src, dst = outer_class(parts[0]), outer_class(parts[2])
        if src.startswith(prefix):
            g.add_node(src)
        if src.startswith(prefix) and dst.startswith(prefix) and src != dst:
            g.add_edge(src, dst)
    return g


def package_graph(class_g: nx.DiGraph) -> nx.DiGraph:
    pg = nx.DiGraph()
    for c in class_g.nodes:
        pg.add_node(package_of(c))
    for a, b in class_g.edges:
        pa, pb = package_of(a), package_of(b)
        if pa != pb:
            w = pg.get_edge_data(pa, pb, {"weight": 0})["weight"]
            pg.add_edge(pa, pb, weight=w + 1)
    return pg


def instability(class_g: nx.DiGraph) -> dict:
    """Martin's metrics per package: Ca, Ce, I = Ce / (Ca + Ce), counted in classes."""
    ca, ce = {}, {}
    for a, b in class_g.edges:
        pa, pb = package_of(a), package_of(b)
        if pa == pb:
            continue
        ce.setdefault(pa, set()).add(a)   # class in pa depends on something outside
        ca.setdefault(pb, set()).add(a)   # class outside pb depends on pb
    out = {}
    for p in {package_of(c) for c in class_g.nodes}:
        a, e = len(ca.get(p, ())), len(ce.get(p, ()))
        out[p] = {"Ca": a, "Ce": e, "I": e / (a + e) if a + e else 0.0}
    return out


def structural_findings(pkg_g, inst, sizes, th) -> pd.DataFrame:
    """Independent computation of the graph/size-based smells. FeatureConcentration is not covered."""
    rows = []
    for scc in nx.strongly_connected_components(pkg_g):
        if len(scc) > 1:
            members = sorted(scc)
            for p in members:
                rows.append((p, "CyclicDependency", "cycle among: " + ", ".join(members)))
    for p in pkg_g.nodes:
        deps = list(pkg_g.successors(p))
        less_stable = [q for q in deps if inst[q]["I"] > inst[p]["I"]]
        if deps and len(less_stable) / len(deps) > th["unstable_ratio"]:
            rows.append((p, "UnstableDependency",
                         f"I={inst[p]['I']:.2f}; depends on less stable: " + ", ".join(sorted(less_stable))))
    for p, (loc, ntypes) in sizes.items():
        if loc > th["god_component_loc"] or ntypes > th["god_component_classes"]:
            rows.append((p, "GodComponent", f"LOC={loc}, types={ntypes}"))
    return pd.DataFrame(rows, columns=["package", "smell", "evidence"])


def save_graph(pkg_g, inst, path: Path):
    data = {"edges": [[a, b, d["weight"]] for a, b, d in pkg_g.edges(data=True)],
            "nodes": sorted(pkg_g.nodes), "instability": inst}
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")


def load_graph(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    g = nx.DiGraph()
    g.add_nodes_from(data["nodes"])
    for a, b, w in data["edges"]:
        g.add_edge(a, b, weight=w)
    return g, data["instability"]


def graph_context(package: str, pkg_g: nx.DiGraph) -> str:
    """C2 context: raw package edges in P's 1-hop neighbourhood. No metrics (they would leak the answer)."""
    if package not in pkg_g:
        return f"[Dependency graph] Package {package} has no dependencies to other project packages."
    out_n = sorted(pkg_g.successors(package))
    in_n = sorted(pkg_g.predecessors(package))
    hood = set(out_n) | set(in_n) | {package}
    lines = [f"[Package-level dependency graph around {package}]",
             "Each line 'A -> B (n)' means classes in A reference classes in B n times (class-level edges).",
             f"Outgoing from {package}: {len(out_n)} packages; incoming to {package}: {len(in_n)} packages.",
             ""]
    for a, b, d in sorted(pkg_g.subgraph(hood).edges(data=True)):
        lines.append(f"{a} -> {b} ({d['weight']})")
    return "\n".join(lines)
