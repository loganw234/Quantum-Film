#!/bin/bash
# Quantum-Film's front door: one command that answers "does it still hold?"
#
# Adapted from HonestFramework's templates/gate-runner.sh, keeping what it
# argues for:
#   §3  a negative-control stage that must FAIL, for the reason it plants, and
#       fails the run if it passes; its positive twin must pass. So the runner
#       proves on every run that it can say no, and that it can say yes;
#   §4  the stage list is DERIVED from this file's own `stage` calls; there is
#       no second list to drift;
#   §5  every skip is printed BY NAME with a reason, and a skip happens only
#       here, at stage level: a test that skips inside a stage fails it
#       (pytest-stage.sh). --require-all turns skips into failures; an unknown
#       stage name is REFUSED, and so is a selection of no stage at all;
#   §6  a run id of timestamp + pid + commit; per-stage .ok markers; --resume
#       reruns only what has not passed, and REFUSES to cross commits or to
#       run on a dirty tree (two dirty trees of one commit share an id);
#   §7  an append-only JSONL record of every stage verdict.
#
# USAGE
#   bash verify/run.sh                     every stage
#   bash verify/run.sh --budget quick      the everyday cut (make verify-quick)
#   bash verify/run.sh --only golden,fixer by name (refuses unknown names)
#   bash verify/run.sh --require-all       a skipped stage FAILS the run
#   bash verify/run.sh --list              stages, with * on what would run
#   bash verify/run.sh --resume            continue the most recent run
#
# THERE IS NO CACHE ACROSS RUNS: a fresh invocation runs everything again.
set -uo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
STATEROOT="${STATEROOT:-$ROOT/.gate-state}"
export PYTHONIOENCODING=utf-8

ONLY=""; SKIP=""; REQUIRE_ALL=0; LIST=0; RESUME=""; FRESH=0; BUDGET=""

# Named cuts, checked against the derived stage list below.
BUDGET_QUICK=lint,docs,vectors,golden,circuits,decode,client,fixer,pinned,fixer-cli,controls

die () { echo "FATAL: $*" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --only)        [ $# -ge 2 ] || die "--only needs a list"; ONLY="$ONLY,$2"; shift 2;;
    --skip)        [ $# -ge 2 ] || die "--skip needs a list"; SKIP="$SKIP,$2"; shift 2;;
    --budget)      [ $# -ge 2 ] || die "--budget needs quick or full"
                   case "$2" in
                     quick) BUDGET=quick; ONLY="$ONLY,$BUDGET_QUICK";;
                     full)  BUDGET=full;;
                     *) die "--budget: unknown budget '$2' (quick, full)";;
                   esac; shift 2;;
    --require-all) REQUIRE_ALL=1; shift;;
    --list)        LIST=1; shift;;
    --resume)      if [ $# -gt 1 ] && [[ ${2:-} != --* ]]; then RESUME=$2; shift 2
                   else RESUME=last; shift; fi;;
    --fresh)       FRESH=1; shift;;
    -h|--help)     sed -n '2,26p' "$0"; exit 0;;
    *)             die "unknown option $1";;
  esac
done

in_list() {  # name, comma-list
  case ",$2," in *",$1,"*) return 0;; esac
  return 1
}

SELF="${BASH_SOURCE[0]}"
STAGELIST=$(grep -E '^stage [a-z0-9-]+ "' "$SELF" | awk '{print $2}' | tr '\n' ' ')
STAGELIST="${STAGELIST% }"

check_names() {  # <flagname> <comma-list>
  local n
  for n in $(echo "$2" | tr ',' ' '); do
    [ -z "$n" ] && continue
    case " $STAGELIST " in
      *" $n "*) ;;
      *) echo "ERROR: $1 names unknown stage '$n'" >&2
         echo "       stages: $STAGELIST" >&2
         exit 2;;
    esac
  done
}
check_names --only "$ONLY"
check_names --skip "$SKIP"
# `--only ""` (or an unset variable) selects nothing, and a run of zero
# stages is not a pass: the negative control would not even run (verifier-P0 7a).
if [ -n "$ONLY" ] && [ -z "$(printf '%s' "$ONLY" | tr -d ', ')" ]; then
  die "--only names no stage; a run of zero stages is not a pass"
fi

if [ "$LIST" = 1 ]; then
  while IFS=$'\t' read -r _nm _ds; do
    if [ -z "$ONLY" ] || in_list "$_nm" "$ONLY"; then _mk="*"; else _mk=" "; fi
    printf '%s %-10s%s\n' "$_mk" "$_nm" "$_ds"
  done < <(grep -E '^stage [a-z0-9-]+ "' "$SELF" | sed -E 's/^stage ([a-z0-9-]+) +"([^"]*)".*/\1\t\2/')
  echo
  if [ -n "$ONLY" ]; then
    printf '* = would run%s. Unmarked stages are NOT in this selection.\n' "${BUDGET:+ under --budget $BUDGET}"
  else
    echo "* = would run: every stage (no --only, no --budget)."
  fi
  exit 0
fi

# git runs from inside the tree (the cd above), never with -C "$ROOT": under
# MSYS_NO_PATHCONV=1, which Atlas work sets, git.exe cannot read a /c/... path.
# That once made every run "nogit" and never dirty, so a dirty tree passed
# the --resume guard below (found by the lead, 2026-09-25). A tree with a .git
# that git cannot read is refused rather than called "nogit".
if COMMIT=$(git rev-parse --short HEAD 2>/dev/null); then
  STATUS=$(git status --porcelain) || die "git status failed in $ROOT"
  DIRTY=$([ -n "$STATUS" ] && echo "+dirty" || echo "")
elif [ -e "$ROOT/.git" ]; then
  die "git cannot read the repository at $ROOT; a run id needs its commit"
else
  COMMIT=nogit; DIRTY=""
fi
if [ -n "$RESUME" ] && [ "$FRESH" = 1 ]; then die "--resume and --fresh are contradictory"; fi
if [ -n "$RESUME" ] && [ "$COMMIT" = nogit ]; then die "--resume needs a git tree: without one a run id names no tree"; fi
# A dirty tree has no identity: two different dirty trees of one commit share
# an id, and a resumed run once reported PASSED over a failing authority that
# way (verifier-P0 7b). Resuming is for a committed tree only.
if [ -n "$RESUME" ] && [ -n "$DIRTY" ]; then
  die "--resume refuses a dirty tree: its run id cannot say which tree it was. Commit, or run fresh."
fi
if [ -n "$RESUME" ]; then
  if [ "$RESUME" = last ]; then
    RUNID=$(ls -1 "$STATEROOT" 2>/dev/null | sort | tail -n 1)
    [ -n "$RUNID" ] || die "--resume: no previous run under $STATEROOT"
  else
    RUNID=$RESUME
  fi
  case "$RUNID" in
    *-"$COMMIT$DIRTY") ;;
    *) die "run $RUNID was a different tree than $COMMIT$DIRTY; half a run of one tree glued to half a
  run of another is a report about neither. Use --fresh.";;
  esac
else
  RUNID="$(date +%Y%m%d-%H%M%S)-$$-$COMMIT$DIRTY"
fi
RUNDIR="$STATEROOT/$RUNID"
mkdir -p "$STATEROOT"
if [ -z "$RESUME" ]; then
  # Two fresh runs in one second once shared a directory, and the second read
  # the first's .ok markers (verifier-P0 7c). The pid separates them, and a
  # fresh run that finds its directory already there refuses.
  mkdir "$RUNDIR" 2>/dev/null || die "run directory $RUNDIR already exists; a fresh run never reuses markers"
else
  [ -d "$RUNDIR" ] || die "--resume: there is no run $RUNID under $STATEROOT"
fi
JSONL="$RUNDIR/stages.jsonl"

PASSED=0; FAILED=0; SKIPPED=0; CACHED=0
note () { echo "   $*"; }

echo "== run $RUNID"
echo "   commit $COMMIT$DIRTY, python $(python -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || echo '?'), state in $RUNDIR"
[ -n "$BUDGET" ] && echo "   budget $BUDGET"

# stage <name> <description> -- command...
# MUST_FAIL=1 before a stage inverts its verdict: the command must fail.
# MUST_SAY="text" with it: and its log must say why. A control that fails for
# some other reason (a crash, a command line that refuses everything) proves
# nothing about the fault it plants.
stage() {
  local name=$1 desc=$2; shift 3
  local t0 t1 rc verdict="" reason="" expect_fail="${MUST_FAIL:-0}" must_say="${MUST_SAY:-}"
  MUST_FAIL=0; MUST_SAY=""
  if [ -n "$ONLY" ] && ! in_list "$name" "$ONLY"; then
    STAGE_SKIP_REASON=""
    return 0
  fi
  if [ -f "$RUNDIR/$name.ok" ]; then
    CACHED=$((CACHED+1))
    note "$(printf '%-10s %-7s %s' "$name" "ok" "(passed earlier in this run)")"
    echo "{\"stage\":\"$name\",\"verdict\":\"ok-cached\"}" >> "$JSONL"
    STAGE_SKIP_REASON=""
    return 0
  fi
  if in_list "$name" "$SKIP"; then
    verdict=SKIP; reason="requested"
  elif [ -n "${STAGE_SKIP_REASON:-}" ]; then
    verdict=SKIP; reason=$STAGE_SKIP_REASON
  fi
  if [ "$verdict" = SKIP ]; then
    SKIPPED=$((SKIPPED+1))
    note "$(printf '%-10s %-7s %s' "$name" "SKIP" "$reason")"
    echo "{\"stage\":\"$name\",\"verdict\":\"skip\",\"reason\":\"$reason\"}" >> "$JSONL"
    [ "$REQUIRE_ALL" = 1 ] && FAILED=$((FAILED+1))
    STAGE_SKIP_REASON=""
    return 0
  fi
  t0=$(date +%s)
  "$@" > "$RUNDIR/$name.log" 2>&1
  rc=$?
  t1=$(date +%s)
  if [ "$expect_fail" = 1 ]; then
    if [ "$rc" -eq 0 ]; then
      FAILED=$((FAILED+1))
      note "$(printf '%-10s %-7s %s' "$name" "FAIL" "NEGATIVE CONTROL DID NOT FAIL - this runner cannot detect a defect")"
      echo "{\"stage\":\"$name\",\"verdict\":\"control-passed\"}" >> "$JSONL"
      return 1
    fi
    if [ -n "$must_say" ] && ! grep -qF -- "$must_say" "$RUNDIR/$name.log"; then
      : > "$RUNDIR/$name.fail"
      FAILED=$((FAILED+1))
      note "$(printf '%-10s %-7s %s' "$name" "FAIL" "the control failed, but not with \"$must_say\"; see $RUNDIR/$name.log")"
      echo "{\"stage\":\"$name\",\"verdict\":\"control-wrong-reason\",\"rc\":$rc}" >> "$JSONL"
      return 1
    fi
    rc=0
    note "$(printf '%-10s %-7s %s' "$name" "ok" "(the negative control failed, as it must: $desc)")"
  fi
  if [ "$rc" -eq 0 ]; then
    : > "$RUNDIR/$name.ok"
    PASSED=$((PASSED+1))
    [ "$expect_fail" = 1 ] || note "$(printf '%-10s %-7s %3ss  %s' "$name" "ok" "$((t1-t0))" "$desc")"
    echo "{\"stage\":\"$name\",\"verdict\":\"ok\",\"seconds\":$((t1-t0))}" >> "$JSONL"
  else
    : > "$RUNDIR/$name.fail"
    FAILED=$((FAILED+1))
    note "$(printf '%-10s %-7s rc=%s  see %s' "$name" "FAIL" "$rc" "$RUNDIR/$name.log")"
    echo "{\"stage\":\"$name\",\"verdict\":\"fail\",\"rc\":$rc}" >> "$JSONL"
  fi
}

# Set a skip reason for the NEXT stage when what it needs is absent. A
# missing tool must never look like a pass.
need ()      { command -v "$1" >/dev/null 2>&1 || STAGE_SKIP_REASON="$2"; }
need_file () { [ -e "$1" ] || STAGE_SKIP_REASON="$2"; }
need_env ()  { [ -n "${!1:-}" ] || STAGE_SKIP_REASON="$2"; }

# ======================================================================
# THE STAGES. One `stage` line each, the description in double quotes on
# the same line, so the list above is derived from them. A pytest stage runs
# a DIRECTORY, so a new test file joins its stage by where it is saved, and
# tests/docs/test_registry.py fails any test file that no stage runs.
# ======================================================================

stage lint "ruff over the package, the tests and the tools" -- \
  python -m ruff check quantum_film tests tools

stage docs "every link resolves, every document is indexed, every test file is run by a stage" -- \
  bash verify/pytest-stage.sh tests/docs

stage vectors "tests/vectors regenerate byte for byte; measured ones match SHA256SUMS" -- \
  python tools/make_vectors.py --check

stage golden "the authority: its law (planted sampler bugs fail), the margin (premise at 512 bits, planted near-tie), uniforms" -- \
  bash verify/pytest-stage.sh tests/golden

stage circuits "the Givens circuit against the golden kernel; three sabotages must fail" -- \
  bash verify/pytest-stage.sh tests/circuits

stage decode "Atlas's count order against a frozen known-answer run; plain order must fail" -- \
  bash verify/pytest-stage.sh tests/decode

stage client "offline: the Atlas client sends its key to the API host only, and never reads one from the tree" -- \
  bash verify/pytest-stage.sh tests/client

stage fixer "negative records: fixed, checked from the record alone, reproduced, refused by name" -- \
  bash verify/pytest-stage.sh tests/fixer

need_file "${QF_CFT_ROOT:-vendor/cft-fp256}/host/cft.dll" "libcft is not built at ${QF_CFT_ROOT:-vendor/cft-fp256} (CLAUDE.md has the build line)"
stage pinned "libcft binary64 rolls equal the authority's; exact values inside the enclosures; the certificate held to an allowlist; hand-off removed, a near-tie disagrees" -- \
  bash verify/pytest-stage.sh tests/pinned

# §3: the control and its twin. The twin runs the fixer's own command line,
# the one a user runs, on the generated records, and must pass: a command line
# that refused everything would otherwise pass the control (verifier-P0 7d).
stage fixer-cli "the fixer's own command line accepts every generated record" -- \
  python -m quantum_film.fixer check tests/vectors/negative-pauli-4x4-seed1.json \
    tests/vectors/negative-pauli-seed1.json tests/vectors/negative-poisson-seed1.json

# The control must FAIL, and name the digest as the reason: the record has a
# crystal moved and the digest left as it was. If this passes, a moved crystal
# would go unnoticed.
MUST_FAIL=1 MUST_SAY="digest: the record's bytes are not the bytes it was fixed with"
stage controls "a tampered negative MUST be refused by the fixer's own command line" -- \
  python -m quantum_film.fixer check tests/vectors/negative-tampered.json

# The DLL a parcel loads is the one QF_CFT_ROOT names, so that is the one
# checked (verifier-P0 11a); the stage prints its path and SHA-256.
need_file "${QF_CFT_ROOT:-vendor/cft-fp256}/host/cft.dll" "libcft is not built at ${QF_CFT_ROOT:-vendor/cft-fp256} (CLAUDE.md has the build line)"
stage cft "libcft loads, reports ABI 0.14, and one correctly rounded cos matches its known bits" -- \
  python tools/cft_smoke.py

need_env QF_ATLAS_AUTH "no Atlas key configured (QF_ATLAS_AUTH names a header file outside the tree)"
stage atlas "live: the account answers and tomography-api-v2 is on the engine list" -- \
  python tools/atlas_smoke.py

# ======================================================================

echo "== summary"
echo "   passed $PASSED, failed $FAILED, skipped $SKIPPED, cached $CACHED"
echo "   record $JSONL"
if [ $((PASSED + FAILED + SKIPPED + CACHED)) -eq 0 ]; then
  echo "== FAILED: no stage ran"
  exit 1
fi
if [ -n "$ONLY" ] && ! in_list controls "$ONLY"; then
  echo "   (the negative control was not in this selection)"
fi
if [ "$FAILED" -ne 0 ]; then
  echo "== FAILED"
  exit 1
fi
if [ "$SKIPPED" -ne 0 ] && [ "$REQUIRE_ALL" != 1 ]; then
  echo "== PASSED, with $SKIPPED skipped by name above"
  echo "   (--require-all makes a skip a failure)"
  exit 0
fi
echo "== PASSED"
exit 0
