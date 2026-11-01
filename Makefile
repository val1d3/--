PYTHON ?= python
CONFIG ?= config.yaml
STAGE ?= 5

.PHONY: run test lint

run:
	$(PYTHON) src/main.py --config $(CONFIG) --stage $(STAGE)

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m flake8 --max-line-length=79 --max-complexity=10 src tests

export PYTHONPATH := src
