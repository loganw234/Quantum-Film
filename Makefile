# The front door is verify/run.sh; these targets are its budgets, so `make`
# and the runner cannot disagree about what "quick" means.

.PHONY: help verify-quick verify vectors test

help:
	@echo "START HERE, if you changed something and want to know whether it still holds:"
	@echo "  make verify-quick   lint, docs, vectors, golden, circuits, decode, client, fixer, hardware, pinned, develop, compare, the control and its twin"
	@echo "  make verify         everything; pinned and cft skip BY NAME without libcft, the live Atlas stage without a key"
	@echo "  bash verify/run.sh --list   every stage, with * on what a budget selects"
	@echo ""
	@echo "  make vectors        regenerate tests/vectors after a DELIBERATE change, then commit them"
	@echo "  make test           pytest alone - not a verdict; the runner is"

verify-quick:
	bash verify/run.sh --budget quick

verify:
	bash verify/run.sh

vectors:
	python tools/make_vectors.py --write

test:
	python -m pytest -q
