#!/bin/bash
# Clones the repos whose solution type is "sln" in data/screened.tsv and runs Designite on them
# (run on Windows, e.g. in Git Bash).
# Each repo is cloned into repos/<owner>_<repo>/ at its latest tag (repos without tags stay on the latest commit);
# repos that are already cloned are not cloned again.
# Needs:   tools/designite/DesigniteConsole.dll
# Usage:   bash scripts/analyze.sh                        all repos
#          bash scripts/analyze.sh owner/repo [...]       only the given repos
# Output:  data/subjects.csv                  (repo, url, tag, commit) = exactly which version of each repo was analyzed
#          output/designite/<owner>_<repo>/   Designite results per repo
#          output/designite/logs/             restore and Designite console output per repo

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCREENED="$ROOT/data/screened.tsv"
SUBJECTS="$ROOT/data/subjects.csv"
REPOS="$ROOT/repos"
DESIGNITE_DIR="$ROOT/tools/designite"
OUT="$ROOT/output/designite"
RESTORE=true   # run "dotnet restore" first; Designite can't load projects whose dependencies aren't restored

export GIT_TERMINAL_PROMPT=0   # never wait for a password
export GIT_LFS_SKIP_SMUDGE=1   # don't download Git LFS files

# Designite is a Windows program: give it Windows paths (C:\...) when running in Git Bash
winpath() { if command -v cygpath >/dev/null; then cygpath -w "$1"; else echo "$1"; fi; }

# designite <sln> <name>: runs Designite into output/designite/<name>/, fails if Designite reports an exception
designite() {
  local log="$OUT/logs/$2-designite.log"
  rm -rf "$OUT/$2" && mkdir -p "$OUT/$2"
  (cd "$DESIGNITE_DIR" && dotnet ./DesigniteConsole.dll -i "$(winpath "$1")" -o "$(winpath "$OUT/$2")") \
    > "$log" 2>&1 </dev/null && ! grep -q "Exception occurred" "$log"
}

[ -f "$SCREENED" ] || { echo "Missing data/screened.tsv - run scripts/screen.sh first."; exit 1; }
[ -f "$DESIGNITE_DIR/DesigniteConsole.dll" ] || { echo "Missing tools/designite/DesigniteConsole.dll - put Designite there."; exit 1; }
mkdir -p "$REPOS" "$OUT/logs"

ALL=$(tail -n +2 "$SCREENED" | awk -F'\t' '$5 == "sln" { print $1 }')
[ -n "$ALL" ] || { echo "No sln repos in data/screened.tsv."; exit 1; }

# repos given on the command line must be "sln" repos in data/screened.tsv
for r in "$@"; do
  printf '%s\n' "$ALL" | grep -qxF "$r" || echo "$r: not an sln repo in data/screened.tsv, skipped"
done

# all repos: start data/subjects.csv from scratch; only some: replace just their rows
if [ $# -eq 0 ] || [ ! -f "$SUBJECTS" ]; then echo "repo,url,tag,commit" > "$SUBJECTS"; fi

printf '%s\n' "$ALL" | while read -r repo; do
  # no repos given: run all; otherwise only the given ones
  [ $# -eq 0 ] || printf '%s\n' "$@" | grep -qxF "$repo" || continue
  url="https://github.com/$repo"
  name="${repo//\//_}"
  dir="$REPOS/$name"
  echo "$repo"

  # 1) clone at the latest tag
  if [ ! -d "$dir/.git" ]; then
    git clone -q "$url.git" "$dir" </dev/null || { echo "    clone failed, skipped"; rm -rf "$dir"; continue; }
    latest=$(git -C "$dir" tag --sort=-creatordate | head -1)
    [ -n "$latest" ] && git -C "$dir" -c advice.detachedHead=false checkout -q "$latest"
  fi
  tag=$(git -C "$dir" describe --tags --exact-match 2>/dev/null)
  commit=$(git -C "$dir" rev-parse HEAD)
  awk -F, -v r="$repo" '$1 != r' "$SUBJECTS" > "$SUBJECTS.tmp" && mv "$SUBJECTS.tmp" "$SUBJECTS"
  echo "$repo,$url,$tag,$commit" >> "$SUBJECTS"
  echo "    ${tag:-no tag} @ $commit"

  # 2) the .sln closest to the repo root (if there are several)
  sln=$(find "$dir" -name '*.sln' -not -path '*/.git/*' | awk -F/ '{ print NF "\t" $0 }' | sort -n | head -1 | cut -f2-)
  [ -n "$sln" ] || { echo "    no .sln found, skipped"; continue; }
  echo "    ${sln#$dir/}"

  # 3) restore and run Designite
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

echo
echo "Cloned repos: repos/    List: data/subjects.csv    Designite results: output/designite/"
