PYTHON ?= python3
CONFIG ?= config.yaml

.PHONY: run test lint

run:
	$(PYTHON) src/main.py --config $(CONFIG)

test:
    PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m flake8 --max-line-length=79 src tests