#!/usr/bin/env bash
# Publish this folder to GitHub in one step.
#
#   ./publish.sh <your-github-username>
#
# It refuses to publish if anything is wrong: unfilled placeholders, a failing
# verification run, or a stray file that should not be public. Run it as many
# times as you like -- it is safe to re-run after fixing something.

set -euo pipefail

REPO_NAME="dpp-qa-fusion-depth"
cd "$(dirname "$0")"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '\033[1m==> %s\033[0m\n' "$*"; }

if [ $# -lt 1 ]; then
  red "Usage: ./publish.sh <your-github-username>"
  echo "Example:  ./publish.sh turzo"
  exit 1
fi
USER="$1"

# ---------------------------------------------------------------- checks ----
info "1/6  Checking for unfilled placeholders"
if grep -rIn "TODO" --include='*.md' --include='*.cff' --include='*.txt' . 2>/dev/null | grep -v publish.sh; then
  red "Placeholders remain. Fill them in, then re-run."
  exit 1
fi
grn "     none left"

info "2/6  Checking nothing private slipped in"
# Note: "CE-RISE" on its own is NOT in this list. It is the name of the funding
# project and is supposed to appear in the acknowledgment. What must not appear
# is the CE-RISE codebase, which is why the specific folder name is checked.
LEAKS=0
for t in COMPASS ADAPTIVERAG AUTO_COMPOSE CE-RISE-Demo MEMSYM sym_trace; do
  if grep -rIl "$t" . 2>/dev/null | grep -qv publish.sh; then
    red "     found '$t' in: $(grep -rIl "$t" . | grep -v publish.sh | tr '\n' ' ')"
    LEAKS=1
  fi
done
if grep -rIlE "sk-[a-zA-Z0-9]{20}|BEGIN [A-Z ]*PRIVATE KEY" . 2>/dev/null | grep -qv publish.sh; then
  red "     possible credential found"
  LEAKS=1
fi
[ "$LEAKS" -eq 1 ] && { red "Refusing to publish."; exit 1; }
grn "     clean"

info "3/6  Verifying every number still matches the paper"
python3 scripts/verify_all.py | tail -2
grn "     verification passed"

# ------------------------------------------------------------------ git ----
info "4/6  Preparing the local repository"
if [ ! -d .git ]; then
  git init -q
  git branch -M main
  grn "     initialised"
else
  grn "     already a git repository"
fi

git add -A
if git diff --cached --quiet; then
  grn "     nothing new to commit"
else
  git commit -q -m "Data and verification code for the AIPMV 2026 paper

Released per-question results for 6,270 verified product-record questions
across four question-answering configurations, the 645 exclusions with
reasons, and the public-schema evaluation arm.

scripts/verify_all.py recomputes every number the paper reports and checks
it against the paper's own macro file. scripts/analysis_clean.py reports
what changes under stricter grading of the question classes."
  grn "     committed"
fi

info "5/6  Creating the repository on GitHub and uploading"
if ! command -v gh >/dev/null 2>&1; then
  red "The GitHub CLI (gh) is not installed."
  echo "Install it with:  brew install gh    then:  gh auth login"
  echo "Or follow the manual route in ../GITHUB_UPLOAD_GUIDE.md"
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  red "You are not logged in to GitHub."
  echo "Run:  gh auth login"
  exit 1
fi

if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin main
else
  gh repo create "$REPO_NAME" --public --source=. --remote=origin --push \
     --description "Data and verification code for the AIPMV 2026 paper on fusion depth in Digital Product Passport question answering"
fi

info "6/6  Done"
URL="https://github.com/$USER/$REPO_NAME"
grn "     $URL"
echo
echo "Next:"
echo "  1. Open $URL and check the README renders."
echo "  2. Put that URL in the paper: compass_shortpaper/paper/main.tex,"
echo "     Reproducibility section (replace ORG with $USER)."
echo "  3. After acceptance, freeze a citable version:"
echo "       git tag -a v1.0 -m 'Version accompanying the AIPMV 2026 paper'"
echo "       git push origin v1.0"
