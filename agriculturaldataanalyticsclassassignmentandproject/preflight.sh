#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${WORK_DIR:-$ROOT/.external}"
LOG="${LOG:-$ROOT/preflight.log}"

exec > >(tee "$LOG") 2>&1

failures=0
check() {
  local description="$1"
  shift
  printf '\n## %s\n' "$description"
  if "$@"; then
    printf 'PASS: %s\n' "$description"
  else
    printf 'FAIL: %s\n' "$description"
    failures=$((failures + 1))
  fi
}

printf '# Assignment environment preflight\n'
printf 'UTC timestamp: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf 'Repository: %s\n' "$ROOT"

check "Poppler pdftotext is installed" pdftotext -v
check "Assignment PDFs are present" bash -c \
  'compgen -G "$1/*.pdf" >/dev/null' _ "$ROOT"

mkdir -p "$WORK_DIR"
clone_or_update() {
  local url="$1" branch="$2" destination="$3"
  if [[ -d "$destination/.git" ]]; then
    git -C "$destination" fetch origin "$branch" &&
      git -C "$destination" checkout "$branch" &&
      git -C "$destination" pull --ff-only
  else
    git clone --branch "$branch" --single-branch "$url" "$destination"
  fi
}

check "agent-project branch is accessible" clone_or_update \
  "https://github.com/SuperiorByteWorks-LLC/agent-project.git" \
  "feat/agri-skills-for-agent-project" "$WORK_DIR/agent-project"
check "ag-skills branch is accessible" clone_or_update \
  "https://github.com/borealBytes/ag-skills.git" \
  "skills-content" "$WORK_DIR/ag-skills"

printf '\n# Result\n'
if (( failures )); then
  printf 'BLOCKED: %d prerequisite check(s) failed.\n' "$failures"
  exit 1
fi
printf 'READY: all prerequisites passed.\n'

