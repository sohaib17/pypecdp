# Minimal makefile for Sphinx documentation

SPHINXBUILD   = sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

help:
	@echo "  html       to make standalone HTML files"
	@echo "  clean      to remove build artifacts"

html:
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)/html"
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR)/html."

clean:
	rm -rf $(BUILDDIR)

.PHONY: help html clean
