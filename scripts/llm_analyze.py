"""Asks an LLM to detect the architectural smells of each repo in repos/ (same code version and projects as Designite).
The LLM gets every .cs file of the C# projects in the .sln closest to the repo root, and prompts/arch_smells.md as system prompt.
With --shots N it first sees the N worked examples in prompts/examples/1..N (code as a user turn, answer.json as reply).
With --history it also gets a summary of the repo's git history up to the analyzed commit (see history.py), 0-shot only.
Needs:   repos cloned by scripts/analyze.sh, pip install -r requirements.txt, and ANTHROPIC_API_KEY in .env (see .env-example)
Usage:   python scripts/llm_analyze.py [--shots N]                      all repos with Designite results (default N = 0)
         python scripts/llm_analyze.py [--shots N] owner/repo [...]     only the given repos
         python scripts/llm_analyze.py --history owner/repo [...]       code + git history, only the given repos
Output:  output/llm/<N>shot/<owner>_<repo>/ArchSmells.csv   one row per smell instance, like Designite's *_ArchSmells.csv
         output/llm/<N>shot/<owner>_<repo>/response.json    model, shots, token usage and the raw answer
         output/llm/history/<owner>_<repo>/                 the same for --history, plus history.md (the summary given)
"""
import argparse
import csv
import json
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

import history

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
OUT = ROOT / "output" / "llm"
MODEL = "claude-opus-5-5"
EFFORT = "high"
SMELLS = ["Cyclic Dependency", "Unstable Dependency", "Ambiguous Interface", "God Component",
          "Feature Concentration", "Scattered Functionality", "Dense Structure"]
MIN_COMMITS = 10  # --history skips repos with fewer commits changing the analyzed files
SYSTEM = (ROOT / "prompts" / "arch_smells.md").read_text(encoding="utf-8")
EXAMPLES = sorted((p for p in (ROOT / "prompts" / "examples").iterdir() if p.is_dir()), key=lambda p: int(p.name))


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


def prompt(repo_dir, project_files, history_text=""):
    parts = []
    for name, files in project_files.items():
        parts.append(f'<project name="{name}">')
        for f in files:
            code = f.read_text(encoding="utf-8-sig", errors="replace")
            parts.append(f'<file path="{f.relative_to(repo_dir).as_posix()}">\n{code}\n</file>')
        parts.append("</project>")
    if history_text:
        parts.append(history_text)
    parts.append(f"Detect the architectural smells in the C# projects above: {', '.join(project_files)}.")
    return "\n".join(parts)


def messages(repo_dir, project_files, shots, history_text=""):
    """The first `shots` examples as user/assistant turns (each project is a folder of the example), then the repo."""
    turns = []
    for example in EXAMPLES[:shots]:
        example_files = {p.name: sorted(p.rglob("*.cs")) for p in sorted(example.iterdir()) if p.is_dir()}
        turns += [{"role": "user", "content": prompt(example, example_files)},
                  {"role": "assistant", "content": (example / "answer.json").read_text(encoding="utf-8")}]
    return turns + [{"role": "user", "content": prompt(repo_dir, project_files, history_text)}]


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


def analyze(client, repo_dir, project_files, shots, history_text=""):
    with client.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=SYSTEM,
        messages=messages(repo_dir, project_files, shots, history_text),
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT,
                       "format": {"type": "json_schema", "schema": schema(list(project_files))}},
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason != "end_turn":
        raise RuntimeError(f"model stopped with '{message.stop_reason}'")
    return message, json.loads(next(b.text for b in message.content if b.type == "text"))["smells"]


def main(selected, shots, with_history):
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

        history_text = ""
        if with_history:
            history_text, n_commits = history.summary(repo_dir, s["commit"], project_files)
            if n_commits < MIN_COMMITS:
                print(f"    only {n_commits} commits change the analyzed files (< {MIN_COMMITS}), skipped")
                continue
            print(f"    history: {n_commits} commits")

        try:
            message, smells = analyze(client, repo_dir, project_files, shots, history_text)
        except (anthropic.APIError, RuntimeError) as e:
            print(f"    LLM failed: {e}")
            continue

        out = OUT / ("history" if with_history else f"{shots}shot") / name
        out.mkdir(parents=True, exist_ok=True)
        if with_history:
            (out / "history.md").write_text(history_text + "\n", encoding="utf-8")
        with open(out / "ArchSmells.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Smell", "Project", "Namespace", "Description", "Participating classes"])
            for i in smells:
                w.writerow([i["smell"], i["project"], i["namespace"], i["description"],
                            "; ".join(i["participating_classes"])])
        (out / "response.json").write_text(json.dumps(
            {"repo": s["repo"], "commit": s["commit"], "model": message.model, "effort": EFFORT, "shots": shots,
             "history": with_history, "usage": message.usage.model_dump(), "smells": smells}, indent=2), encoding="utf-8")
        print(f"    {len(smells)} smells -> {out.relative_to(ROOT).as_posix()}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="*", help="owner/repo as in data/subjects.csv (default: all with Designite results)")
    parser.add_argument("--shots", type=int, default=0, choices=range(len(EXAMPLES) + 1),
                        help="number of worked examples from prompts/examples/ shown before the repo")
    parser.add_argument("--history", action="store_true",
                        help="also give the LLM a summary of the git history (0-shot only, repos must be given)")
    args = parser.parse_args()
    if args.history and args.shots:
        parser.error("--history is compared with the 0-shot baseline and cannot be combined with --shots")
    if args.history and not args.repos:
        parser.error("--history needs the repos to analyze, e.g. --history zo1223/OpaiTV")
    main(args.repos, args.shots, args.history)
