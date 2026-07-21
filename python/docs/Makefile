# Build both independent Sphinx documentation roots.

SPHINXOPTS ?=
ROOTS      = sdk cli

.PHONY: help html linkcheck clean

help:
	@echo "Build targets: html, linkcheck, clean"

html:
	@for root in $(ROOTS); do $(MAKE) -C $$root html SPHINXOPTS="$(SPHINXOPTS)" || exit $$?; done

linkcheck:
	@for root in $(ROOTS); do $(MAKE) -C $$root linkcheck SPHINXOPTS="$(SPHINXOPTS)" || exit $$?; done

clean:
	@for root in $(ROOTS); do $(MAKE) -C $$root clean || exit $$?; done
