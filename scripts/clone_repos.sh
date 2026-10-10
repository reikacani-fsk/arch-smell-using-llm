#!/bin/bash
# Clones every repo whose solution type is "sln" in data/screened.tsv into repos/<owner>_<repo>/
# and checks out its latest tag (repos without tags stay on the latest commit).
# Usage:   bash scripts/clone_repos.sh
# Output:  data/subjects.csv  (repo, url, tag, commit) = exactly which version of each repo was cloned

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCREENED="$ROOT/data/screened.tsv"
SUBJECTS="$ROOT/data/subjects.csv"
REPOS="$ROOT/repos"

export GIT_TERMINAL_PROMPT=0   # never wait for a password
export GIT_LFS_SKIP_SMUDGE=1   # don't download Git LFS files

[ -f "$SCREENED" ] || { echo "Missing data/screened.tsv - run scripts/screen.sh first."; exit 1; }
mkdir -p "$REPOS"
echo "repo,url,tag,commit" > "$SUBJECTS"

tail -n +2 "$SCREENED" | awk -F'\t' '$5 == "sln" { print $1 }' | while read -r repo; do
  url="https://github.com/$repo"
  dir="$REPOS/${repo//\//_}"
  echo "$repo"
  if [ ! -d "$dir/.git" ]; then
    git clone -q "$url.git" "$dir" </dev/null || { echo "    clone failed, skipped"; rm -rf "$dir"; continue; }
    latest=$(git -C "$dir" tag --sort=-creatordate | head -1)
    [ -n "$latest" ] && git -C "$dir" -c advice.detachedHead=false checkout -q "$latest"
  fi
  tag=$(git -C "$dir" describe --tags --exact-match 2>/dev/null)
  commit=$(git -C "$dir" rev-parse HEAD)
  echo "$repo,$url,$tag,$commit" >> "$SUBJECTS"
  echo "    ${tag:-no tag} @ $commit"
done

echo
echo "Cloned repos: repos/    List: data/subjects.csv"
