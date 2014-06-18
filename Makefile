PYTHON = python
NOSETESTS = nosetests


.PHONY: build force test clean distclean

build:
	$(PYTHON) setup.py build_ext --inplace

force:
	$(PYTHON) setup.py build_ext --inplace -f

debug:
	$(PYTHON) setup.py build_ext --inplace -f -g

test:
	-rm -rf moa/tests/build
	$(NOSETESTS) moa/tests

install:
	python setup.py install
