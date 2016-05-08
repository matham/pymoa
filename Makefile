PYTHON = python
NOSETESTS = nosetests


.PHONY: test

test:
	-rm -rf moa/tests/build
	$(NOSETESTS) moa/tests

install:
	python setup.py install
