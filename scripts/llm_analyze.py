"""Asks an LLM to detect the architectural smells of each repo in repos/ (same code version and projects as Designite).
The LLM gets every .cs file of the C# projects in the .sln closest to the repo root, and prompts/arch_smells.md as system prompt.
Needs:   repos cloned by scripts/analyze.sh, pip install -r requirements.txt, and ANTHROPIC_API_KEY in .env (see .env-example)
Usage:   python scripts/llm_analyze.py                      all repos with Designite results
         python scripts/llm_analyze.py owner/repo [...]     only the given repos
Output:  output/llm/<owner>_<repo>/ArchSmells.csv   one row per smell instance, like Designite's *_ArchSmells.csv
         output/llm/<owner>_<repo>/response.json    model, token usage and the raw answer
"""
import csv
import json
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
OUT = ROOT / "output" / "llm"
MODEL = "claude-opus-5-5"
EFFORT = "high"
SMELLS = ["Cyclic Dependency", "Unstable Dependency", "Ambiguous Interface", "God Component",
          "Feature Concentration", "Scattered Functionality", "Dense Structure"]
SYSTEM = (ROOT / "prompts" / "arch_smells.md").read_text(encoding="utf-8")


def projects(repo_dir):
    """{project name: [.cs files]} of the .sln closest to the repo root, the one analyze.sh gives Designite."""
    slns = sorted(repo_dir.rglob("*.sln"), key=lambda p: (len(p.parts), str(p)))
    if not slns:
        return {}
    text = slns[0].read_text(encoding="utf-8-sig", errors="replace")
    result = {}
    for name, csproj in re.findall(r'^Project\("[^"]*"\)\s*=\s*"([^"]+)",\s*"([^"]+\.csproj)"', text, re.M):
        project_dir = (slns[0].parent / csproj.replace("\\", "/")).parent
        files = sorted(p for p in project_dir.rglob("*.cs")
                       if not {"bin", "obj"} & set(p.relative_to(project_dir).parts))
        if files:
            result[name] = files
    return result


def prompt(repo_dir, project_files):
    parts = []
    for name, files in project_files.items():
        parts.append(f'<project name="{name}">')
        for f in files:
            code = f.read_text(encoding="utf-8-sig", errors="replace")
            parts.append(f'<file path="{f.relative_to(repo_dir).as_posix()}">\n{code}\n</file>')
        parts.append("</project>")
    parts.append(f"Detect the architectural smells in the C# projects above: {', '.join(project_files)}.")
    return "\n".join(parts)


def schema(project_names):
    instance = {
        "type": "object",
        "additionalProperties": False,
        "required": ["smell", "project", "namespace", "description", "participating_classes"],
        "properties": {
            "smell": {"type": "string", "enum": SMELLS},
            "project": {"type": "string", "enum": project_names},
            "namespace": {"type": "string"},
            "description": {"type": "string"},
            "participating_classes": {"type": "array", "items": {"type": "string"}},
        },
    }
    return {"type": "object", "additionalProperties": False, "required": ["smells"],
            "properties": {"smells": {"type": "array", "items": instance}}}


def analyze(client, repo_dir, project_files):
    with client.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt(repo_dir, project_files)}],
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT,
                       "format": {"type": "json_schema", "schema": schema(list(project_files))}},
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason != "end_turn":
        raise RuntimeError(f"model stopped with '{message.stop_reason}'")
    return message, json.loads(next(b.text for b in message.content if b.type == "text"))["smells"]


def main(selected):
    with open(ROOT / "data" / "subjects.csv", newline="") as f:
        subjects = list(csv.DictReader(f))
    for r in selected:
        if r not in {s["repo"] for s in subjects}:
            print(f"{r}: not in data/subjects.csv, skipped")
    client = anthropic.Anthropic()

    for s in subjects:
        name = s["repo"].replace("/", "_")
        if selected and s["repo"] not in selected:
            continue
        if not selected and not (ROOT / "output" / "designite" / name).is_dir():
            continue
        print(s["repo"])
        repo_dir = ROOT / "repos" / name
        if not repo_dir.is_dir():
            print("    not in repos/ - run scripts/analyze.sh first, skipped")
            continue
        project_files = projects(repo_dir)
        if not project_files:
            print("    no C# projects found, skipped")
            continue
        print(f"    {len(project_files)} projects, {sum(map(len, project_files.values()))} .cs files")

        try:
            message, smells = analyze(client, repo_dir, project_files)
        except (anthropic.APIError, RuntimeError) as e:
            print(f"    LLM failed: {e}")
            continue

        out = OUT / name
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "ArchSmells.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Smell", "Project", "Namespace", "Description", "Participating classes"])
            for i in smells:
                w.writerow([i["smell"], i["project"], i["namespace"], i["description"],
                            "; ".join(i["participating_classes"])])
        (out / "response.json").write_text(json.dumps(
            {"repo": s["repo"], "commit": s["commit"], "model": message.model, "effort": EFFORT,
             "usage": message.usage.model_dump(), "smells": smells}, indent=2), encoding="utf-8")
        print(f"    {len(smells)} smells -> output/llm/{name}/")


if __name__ == "__main__":
    main(sys.argv[1:])
