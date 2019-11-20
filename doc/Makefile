BUILDDIR = ../gh-pages

html: $(BUILDDIR) conf.py index.rst
	sphinx-build -b html . "$(BUILDDIR)"

$(BUILDDIR):
	git clone -b gh-pages --single-branch \
		"$(shell git config --get remote.origin.url)" "$(BUILDDIR)"
