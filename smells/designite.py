"""Parse DesigniteJava (Enterprise) architecture-smell CSV output."""
import re
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


def load_architecture_smells(csv_path) -> pd.DataFrame:
    """Return a DataFrame with columns: package, smell, cause.

    Column names are matched loosely ("Package Name", "Architecture Smell", "Cause of the Smell")
    because they differ between Designite versions. Check your real CSV once and adapt if needed.
    """
    df = pd.read_csv(csv_path, encoding="utf-8", encoding_errors="replace")
    df.columns = [c.strip() for c in df.columns]
    pkg = _find(df.columns, "package", "component", "namespace")
    smell = _find(df.columns, "smell", exclude=("cause", "description"))
    cause = _find(df.columns, "cause", "description")
    if not pkg or not smell:
        raise ValueError(f"Cannot identify package/smell columns in {list(df.columns)}")
    out = pd.DataFrame({
        "package": df[pkg].astype(str).str.strip(),
        "smell": df[smell].map(canonical_smell),
        "cause": df[cause].astype(str) if cause else "",
    })
    return out.drop_duplicates(["package", "smell"]).reset_index(drop=True)
