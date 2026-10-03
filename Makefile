# streamdock-n3-linux: source-tree installer for distro packagers.
#
# Typical packaging use:
#   make build               # build a wheel under dist/
#   make DESTDIR=$pkgdir DEVICE=hotspotekusb install
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
DEVICE         ?=

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
	@echo "  install-data  Install system data files (set DEVICE=mirabox|hotspotekusb to skip prompt)"
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
	@set -eu; \
	device="$(DEVICE)"; \
	mirabox=0; hotspotekusb=0; default=""; \
	for vendor_file in /sys/bus/usb/devices/*/idVendor; do \
		[ -r "$$vendor_file" ] || continue; \
		vendor=$$(cat "$$vendor_file" 2>/dev/null || true); \
		case "$$vendor" in 6603) mirabox=1 ;; 5548) hotspotekusb=1 ;; esac; \
	done; \
	if [ -z "$$device" ]; then \
		if [ "$$mirabox" -eq 1 ] && [ "$$hotspotekusb" -eq 0 ]; then default=1; \
		elif [ "$$hotspotekusb" -eq 1 ] && [ "$$mirabox" -eq 0 ]; then default=2; fi; \
		if [ "$$mirabox" -eq 1 ] || [ "$$hotspotekusb" -eq 1 ]; then \
			printf 'Detected supported USB device(s):'; \
			[ "$$mirabox" -eq 0 ] || printf ' Mirabox'; \
			[ "$$hotspotekusb" -eq 0 ] || printf ' HOTSPOTEKUSB'; \
			printf '\n'; \
		else printf 'No supported Stream Dock detected over USB.\n'; fi; \
		printf '  1) Mirabox%s\n' "$$([ "$$mirabox" -eq 1 ] && printf ' (detected)')"; \
		printf '  2) HOTSPOTEKUSB%s\n' "$$([ "$$hotspotekusb" -eq 1 ] && printf ' (detected)')"; \
		while :; do \
			if [ "$$default" = 1 ]; then \
				printf 'Select device [1/2] (Enter = Mirabox): '; \
			elif [ "$$default" = 2 ]; then \
				printf 'Select device [1/2] (Enter = HOTSPOTEKUSB): '; \
			else printf 'Select device [1/2]: '; fi; \
			IFS= read -r answer || { printf '\nNo device selected.\n' >&2; exit 1; }; \
			[ -n "$$answer" ] || answer="$$default"; \
			case "$$answer" in \
				1|mirabox|m) device=mirabox; break ;; \
				2|hotspotekusb|hotspot|h) device=hotspotekusb; break ;; \
				*) printf 'Please enter 1 or 2.\n' ;; \
			esac; \
		done; \
	fi; \
	case "$$device" in \
		mirabox) rule=99-streamdock-mirabox.rules ;; \
		hotspotekusb) rule=99-streamdock-hotspotekusb.rules ;; \
		*) printf 'Invalid DEVICE: %s (use mirabox or hotspotekusb).\n' "$$device" >&2; exit 2 ;; \
	esac; \
	printf 'Installing %s udev rule as %s/%s\n' "$$device" '$(DESTDIR)$(UDEV_RULES_DIR)' '$(UDEV_RULE)'; \
	$(INSTALL) -Dm0644 "$(PKG_DATA)/$$rule" "$(DESTDIR)$(UDEV_RULES_DIR)/$(UDEV_RULE)"
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
