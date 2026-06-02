# streamdock-n3-linux: source-tree installer for distro packagers.
#
# Typical packaging use:
#   make build               # build a wheel under dist/
#   make DESTDIR=$pkgdir install
#
# For local development install, prefer:
#   pipx install --force .
#   sudo streamdock-n3-install

PYTHON         ?= python3
PIP            ?= $(PYTHON) -m pip
PREFIX         ?= /usr
BINDIR         ?= $(PREFIX)/bin
DATAROOTDIR    ?= $(PREFIX)/share
APPLICATIONS_DIR ?= $(DATAROOTDIR)/applications
SYSTEMD_USER_DIR ?= $(PREFIX)/lib/systemd/user
UDEV_RULES_DIR ?= /etc/udev/rules.d

INSTALL        ?= install
DESTDIR        ?=

PKG_DATA       := src/streamdock_n3/_data
UDEV_RULE      := 99-streamdock.rules
SERVICE_FILE   := streamdock-n3.service
DESKTOP_FILE   := streamdock-n3-gui.desktop

.PHONY: help build install install-data install-python uninstall clean test lint

help:
	@echo "Targets:"
	@echo "  build         Build wheel + sdist under dist/"
	@echo "  install       Install wheel and system data files (uses pip, udev rule, systemd unit, desktop)"
	@echo "  install-data  Install only system data files (udev/service/desktop)"
	@echo "  uninstall     Remove system data files (does not touch Python install)"
	@echo "  test          Run pytest"
	@echo "  lint          Run ruff + mypy"
	@echo "  clean         Remove build artifacts"

build:
	$(PYTHON) -m build

install: install-python install-data

install-python:
	$(PIP) install --no-deps --no-build-isolation --prefix=$(PREFIX) --root=$(DESTDIR)/ .

install-data:
	$(INSTALL) -Dm0644 $(PKG_DATA)/$(UDEV_RULE) $(DESTDIR)$(UDEV_RULES_DIR)/$(UDEV_RULE)
	sed 's|@BIN@|$(BINDIR)|g' $(PKG_DATA)/$(SERVICE_FILE) \
		| $(INSTALL) -Dm0644 /dev/stdin $(DESTDIR)$(SYSTEMD_USER_DIR)/$(SERVICE_FILE)
	sed 's|@BIN@|$(BINDIR)|g' $(PKG_DATA)/$(DESKTOP_FILE) \
		| $(INSTALL) -Dm0644 /dev/stdin $(DESTDIR)$(APPLICATIONS_DIR)/$(DESKTOP_FILE)

uninstall:
	rm -f $(DESTDIR)$(UDEV_RULES_DIR)/$(UDEV_RULE)
	rm -f $(DESTDIR)$(SYSTEMD_USER_DIR)/$(SERVICE_FILE)
	rm -f $(DESTDIR)$(APPLICATIONS_DIR)/$(DESKTOP_FILE)

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy src/streamdock_n3

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache
