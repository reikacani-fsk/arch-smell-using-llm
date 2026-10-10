#!/bin/bash
# Runs Designite on the repos listed in data/subjects.csv (run on Windows, e.g. in Git Bash).
# Needs:   tools/designite/DesigniteConsole.dll
# Usage:   bash scripts/run_designite.sh                        all repos in data/subjects.csv
#          bash scripts/run_designite.sh owner/repo [...]       only the given repos
# Output:  output/designite/<owner>_<repo>/   Designite results per repo
#          output/designite/logs/             restore and Designite console output per repo

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DESIGNITE_DIR="$ROOT/tools/designite"
SUBJECTS="$ROOT/data/subjects.csv"
OUT="$ROOT/output/designite"
RESTORE=true   # run "dotnet restore" first; Designite can't load projects whose dependencies aren't restored

# Designite is a Windows program: give it Windows paths (C:\...) when running in Git Bash
winpath() { if command -v cygpath >/dev/null; then cygpath -w "$1"; else echo "$1"; fi; }

# designite <sln> <name>: runs Designite into output/designite/<name>/, fails if Designite reports an exception
designite() {
  local log="$OUT/logs/$2-designite.log"
  rm -rf "$OUT/$2" && mkdir -p "$OUT/$2"
  (cd "$DESIGNITE_DIR" && dotnet ./DesigniteConsole.dll -i "$(winpath "$1")" -o "$(winpath "$OUT/$2")") \
    > "$log" 2>&1 </dev/null && ! grep -q "Exception occurred" "$log"
}

[ -f "$DESIGNITE_DIR/DesigniteConsole.dll" ] || { echo "Missing tools/designite/DesigniteConsole.dll - put Designite there."; exit 1; }
[ -f "$SUBJECTS" ] || { echo "Missing data/subjects.csv - run scripts/clone_repos.sh first."; exit 1; }
mkdir -p "$OUT/logs"

# repos given on the command line must be in data/subjects.csv
for r in "$@"; do
  cut -d, -f1 "$SUBJECTS" | grep -qxF "$r" || echo "$r: not in data/subjects.csv, skipped"
done

tail -n +2 "$SUBJECTS" | while IFS=, read -r repo url tag commit; do
  # no repos given: run all; otherwise only the given ones
  [ $# -eq 0 ] || printf '%s\n' "$@" | grep -qxF "$repo" || continue
  name="${repo//\//_}"
  dir="$ROOT/repos/$name"
  # the .sln closest to the repo root (if there are several)
  sln=$(find "$dir" -name '*.sln' -not -path '*/.git/*' | awk -F/ '{ print NF "\t" $0 }' | sort -n | head -1 | cut -f2-)
  [ -n "$sln" ] || { echo "$repo: no .sln found, skipped"; continue; }
  echo "$repo  ->  ${sln#$dir/}"

  if $RESTORE; then
    dotnet restore "$(winpath "$sln")" > "$OUT/logs/$name-restore.log" 2>&1 </dev/null \
      || echo "    restore failed (see output/designite/logs/$name-restore.log)"
  fi

  if designite "$sln" "$name"; then
    echo "    done -> output/designite/$name/"
  elif $RESTORE; then
    # some repos make Designite crash once restored: remove the restore output (obj/ folders) and retry without it
    echo "    Designite failed after restore, retrying without restore"
    mv "$OUT/logs/$name-designite.log" "$OUT/logs/$name-designite-restored.log"
    git -C "$dir" clean -fdxq
    designite "$sln" "$name" \
      && echo "    done (without restore) -> output/designite/$name/" \
      || echo "    Designite failed (see output/designite/logs/$name-designite.log)"
  else
    echo "    Designite failed (see output/designite/logs/$name-designite.log)"
  fi
done
