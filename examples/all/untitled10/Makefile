PYTHON ?= python
CYTHON ?= cython
PYTEST ?= pytest


all: clean inplace test

build:
	mkdir -p build
	cd build && cmake .. && make

clean:
	$(PYTHON) setup.py clean
	rm -rf dist


inplace:
	$(PYTHON) setup.py build_ext -i


test-code: in
	$(PYTEST) --showlocals -v engine --durations=20


test-sphinxext:
	$(PYTEST) --showlocals -v doc/sphinxext/

test-doc:
	$(PYTEST) $(shell find doc -name '*.rst' | sort)

test-code-parallel: in
	$(PYTEST) -n auto --showlocals -v engine --durations=20

test-coverage:
	rm -rf coverage .coverage
	$(PYTEST) engine --showlocals -v --cov=engine --cov-report=html:coverage

cctest: build
	cd build && ctest --verbose

test-coverage-parallel:
	rm -rf coverage .coverage .coverage.*
	$(PYTEST) engine -n auto --showlocals -v --cov=engine --cov-report=html:coverage

test: test-code test-sphinxext test-doc

trailing-spaces:
	find engine -name "*.py" -exec sed -i 's/[ \t]*$$//' {} \;

cython:
	python setup.py build_src

doc: inplace
	$(MAKE) -C doc html

doc-noplot: inplace
	$(MAKE) -C doc html-noplot

code-analysis:
	build_tools/linting.sh