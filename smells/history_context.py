"""C3 context: recent commits touching a package (messages, churn, co-changed packages).

Uses `git log` directly: it is faster and simpler than PyDriller for this read-only use,
and pathspecs restrict history to the package's own files (not its subpackages).
"""
import subprocess
from collections import Counter
from pathlib import Path

SEP = "\x1e"


def _rel_package_dir(project_root: Path, source_dir: Path, package: str) -> str:
    rel = source_dir.relative_to(project_root).as_posix()
    return f"{rel}/{package.replace('.', '/')}"


def _path_to_package(path: str, source_rels) -> str | None:
    for rel in source_rels:
        if path.startswith(rel + "/") and path.endswith(".java"):
            return path[len(rel) + 1:].rsplit("/", 1)[0].replace("/", ".")
    return None


def package_history(project_root: Path, source_dirs, package: str, release: str, n: int,
                    index: dict | None = None) -> str:
    """Java: package = directory. C#: namespaces need not follow folders, so pass the source `index`
    and the package's files (as of the release) are used as pathspecs instead."""
    source_rels = [Path(d).relative_to(project_root).as_posix() for d in source_dirs]
    specs = [f":(glob){_rel_package_dir(project_root, Path(d), package)}/*.java" for d in source_dirs]
    file_pkg = None
    if index is not None:
        file_pkg = {f.path.relative_to(project_root).as_posix(): pkg for pkg, files in index.items() for f in files}
        specs = [f":(literal){p}" for p, pkg in sorted(file_pkg.items()) if pkg == package]
        if not specs:
            return f"[History] No source files for {package}."
    cmd = ["git", "-C", str(project_root), "log", release, f"-n{n}", "--no-merges", "--full-diff",
           f"--format={SEP}%h|%ad|%s", "--date=short", "--numstat", "--"] + specs
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        return f"[History] unavailable: {res.stderr.strip()[:200]}"
    commits, cochange = [], Counter()
    for block in res.stdout.split(SEP)[1:]:
        lines = [l for l in block.strip().splitlines() if l.strip()]
        header, stats = lines[0], lines[1:]
        added = deleted = own_files = 0
        touched = set()
        for s in stats:
            parts = s.split("\t")
            if len(parts) != 3:
                continue
            a, d, path = parts
            pkg = file_pkg.get(path) if file_pkg is not None else _path_to_package(path, source_rels)
            if pkg == package:
                own_files += 1
                added += int(a) if a.isdigit() else 0
                deleted += int(d) if d.isdigit() else 0
            elif pkg:
                touched.add(pkg)
        cochange.update(touched)
        commits.append(f"{header} | files in package: {own_files}, +{added}/-{deleted}")
    if not commits:
        return f"[History] No commits touching {package} up to {release} (or shallow clone)."
    lines = [f"[Last {len(commits)} commits touching {package} up to {release}]"] + commits
    if cochange:
        lines.append("Packages most often changed in the same commits: " +
                     ", ".join(f"{p} ({c})" for p, c in cochange.most_common(8)))
    return "\n".join(lines)
