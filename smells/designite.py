"""Run Designite and parse its architecture-smell CSV output (DesigniteJava and Designite for C#)."""
import re
from pathlib import Path

import pandas as pd

KNOWN = ["CyclicDependency", "UnstableDependency", "GodComponent", "FeatureConcentration",
         "ScatteredFunctionality", "AmbiguousInterface", "DenseStructure"]


def canonical_smell(name: str) -> str:
    key = re.sub(r"[^a-z]", "", str(name).lower())
    for k in KNOWN:
        if k.lower() == key:
            return k
    return re.sub(r"\W", "", str(name))


def _find(cols, *words, exclude=()):
    for c in cols:
        lc = c.lower()
        if any(w in lc for w in words) and not any(x in lc for x in exclude):
            return c
    return None


def designite_command(cfg) -> tuple[list[str], Path, Path]:
    """(command, working dir, output dir) for the `designite:` section of the config.

    C#:   cd <DesigniteConsole folder>;  dotnet DesigniteConsole.dll -i <abs .sln> -o <abs output dir>
    Java: cd <tools>;                    java -jar DesigniteJava.jar -i <abs source dir> -o <abs output dir>
    Paths are made absolute because Designite runs from its own folder (it loads its BuildHost and
    writes Logs/ there).
    """
    d = cfg["designite"]
    tool, inp, out = ((cfg.base / d[k]).resolve() for k in ("tool", "input", "output_dir"))
    if tool.suffix == ".jar":
        cmd = ["java", "-jar", tool.name, "-i", str(inp), "-o", str(out)]
    else:
        cmd = ["dotnet", tool.name, "-i", str(inp), "-o", str(out)]
    return cmd, tool.parent, out


def arch_smell_csvs(path) -> list[Path]:
    """`path` is a CSV file or a Designite output folder; a folder is searched for the
    architecture-smell CSV(s), e.g. ArchitectureSmells.csv or Designite_<Project>_ArchSmells.csv
    (one per project of a solution)."""
    path = Path(path)
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    return sorted(p for p in path.rglob("*.csv")
                  if "arch" in p.name.lower() and "smell" in p.name.lower())


def load_architecture_smells(csv_path) -> pd.DataFrame:
    """Return a DataFrame with columns: package, smell, cause.

    Column names are matched loosely ("Package Name"/"Namespace", "Architecture Smell", "Cause of the Smell")
    because they differ between Designite versions. Check your real CSV once and adapt if needed.
    """
    files = arch_smell_csvs(csv_path)
    if not files:
        raise FileNotFoundError(f"No architecture-smell CSV at {csv_path}")
    return pd.concat([_load_one(f) for f in files]).drop_duplicates(["package", "smell"]).reset_index(drop=True)


def _load_one(csv_path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8", encoding_errors="replace")
    df.columns = [c.strip() for c in df.columns]
    pkg = _find(df.columns, "package", "component", "namespace")
    smell = _find(df.columns, "smell", exclude=("cause", "description"))
    cause = _find(df.columns, "cause", "description")
    if not pkg or not smell:
        raise ValueError(f"Cannot identify package/smell columns in {list(df.columns)} ({csv_path})")
    return pd.DataFrame({
        "package": df[pkg].astype(str).str.strip(),
        "smell": df[smell].map(canonical_smell),
        "cause": df[cause].astype(str) if cause else "",
    })
