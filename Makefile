all: localecompile
LNGS:=`find pretix_eth/locale/ -mindepth 1 -maxdepth 1 -type d -printf "-l %f "`

localecompile:
	django-admin compilemessages

localegen:
	django-admin makemessages --keep-pot -i build -i dist -i "*egg*" $(LNGS)

devserver:
	python -mpretix runserver

devmigrate:
	python -mpretix migrate

.PHONY: all localecompile localegen frontend-install frontend-build frontend-watch build-all

frontend-install:
	cd pretix_eth/static/wc_inject && pnpm install

frontend-build: frontend-install
	cd pretix_eth/static/wc_inject && pnpm run build

frontend-watch:
	cd pretix_eth/static/wc_inject && pnpm run watch

build-all: frontend-build
	@echo 'Run "pip install -e ." to build Python side'
