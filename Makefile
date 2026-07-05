SHELL := /bin/bash
.DEFAULT_GOAL := dev

.PHONY: dev install build strong weak viz field experiments clean clean-all

dev:
	uv sync --dev

install:
	uv sync --locked --dev

build:
	uv build --all-packages

# ── Experiments ──────────────────────────────────────────────────────
# Pass extra CLI args through with ARGS, e.g.:
#   make strong ARGS="--reps 5 --cores 1 2 4"
#   make weak   ARGS="--out results/weak_dev.h5"
#   make viz    ARGS="--out-dir results/assets_v2"
#   make field  ARGS="--h5 results/strong.h5#/strong/heatrs/nx512_ny512/cores1 --gif out.gif"
 
STRONG_OUT  ?= results/strong.h5
WEAK_OUT    ?= results/weak.h5
RESULTS_DIR ?= results/assets
 
strong:
	uv run python scripts/strong_scaling.py --out $(STRONG_OUT) $(ARGS)
 
weak:
	uv run python scripts/weak_scaling.py --out $(WEAK_OUT) $(ARGS)
 
viz:
	uv run heatviz-scaling --strong $(STRONG_OUT) --weak $(WEAK_OUT) --out-dir $(RESULTS_DIR) $(ARGS)
 
field:
	uv run heatviz-field $(ARGS)
 
experiments: strong weak viz

clean:
	rm -rf dist build *.egg-info src/*.egg-info	target
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*$$py.class" -delete
	
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov

clean-all: clean
	rm -rf .venv/
	git clean -fx *.h5 *.pdf

# TODO: add check for enviroment. It should check for uv and rust toolchain and for some libs like below.
# sudo apt install libhdf5-dev pkg-config
