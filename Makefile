SHELL := /bin/bash
.DEFAULT_GOAL := dev

.PHONY: dev install build clean clean-all

dev:
	uv sync --dev

install:
	uv sync --locked --dev

build:
	uv build --all-packages

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
