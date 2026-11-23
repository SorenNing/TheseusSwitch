PYTHON ?= python3
ARCH ?= arm64e
.PHONY: all check build verify clean
# Safe default: no implicit native compilation.
all: check
check:
	$(PYTHON) tools/project.py --output evidence/source-check.json
# Only run after separately authorizing a native build on macOS + Xcode.
build:
	$(PYTHON) tools/build.py --arch $(ARCH)
verify:
	$(PYTHON) tools/verify-dist.py $(ARCH)
clean:
	$(PYTHON) -c "import shutil; shutil.rmtree('build', ignore_errors=True)"
