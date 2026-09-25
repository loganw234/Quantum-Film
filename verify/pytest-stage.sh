#!/bin/bash
# Run pytest on the given paths, and hold it to its own summary line as well
# as its exit code (METHOD §5: exit codes are not reports):
#   - rc must be 0;
#   - the last line must say "<n> passed", with n >= 1 (zero tests collected
#     passing is not a pass);
#   - the summary must name no failure and no error;
#   - every skip is printed with its reason (-rs) so the runner's log names it.
#
# Third-party pytest plugins are switched off: a verdict must not depend on
# what happens to be installed (zarr's plugin imports CuPy on the owner's
# desktop, 2026-09-25).
set -uo pipefail
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
out=$(python -m pytest -q -rs "$@" 2>&1)
rc=$?
echo "$out"
summary=$(printf '%s\n' "$out" | tail -n 1)
if [ "$rc" -ne 0 ]; then
  echo "pytest-stage: pytest exited $rc"
  exit 1
fi
if ! printf '%s\n' "$summary" | grep -Eq '^[1-9][0-9]* passed'; then
  echo "pytest-stage: no '<n> passed' summary line: $summary"
  exit 1
fi
if printf '%s\n' "$summary" | grep -Eq 'failed|error'; then
  echo "pytest-stage: the summary names a failure: $summary"
  exit 1
fi
exit 0
