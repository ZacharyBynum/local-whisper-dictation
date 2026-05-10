.PHONY: check compile lint test shell clean

PYTHON ?= python3

check: compile lint test shell

compile:
	$(PYTHON) -m py_compile bynum_dictate*.py

lint:
	ruff check .

test:
	pytest -q

shell:
	bash -n install.sh

clean:
	rm -rf __pycache__ tests/__pycache__ .pytest_cache .ruff_cache *.egg-info build dist uv.lock
