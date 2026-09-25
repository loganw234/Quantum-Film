# The front door is verify/run.sh; these targets are its budgets, so `make`
# and the runner cannot disagree about what "quick" means.

.PHONY: help verify-quick verify vectors test

help:
	@echo "START HERE, if you changed something and want to know whether it still holds:"
	@echo "  make verify-quick   lint, docs, vectors, golden, circuits, decode, fixer and the negative control"
	@echo "  make verify         everything; the cft and live Atlas stages skip BY NAME when they cannot run"
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
