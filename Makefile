.PHONY: validate test

validate:
	python3 scripts/validate_harness.py
	python3 -m unittest discover -s tests -v

test:
	python3 -m unittest discover -s tests -v
