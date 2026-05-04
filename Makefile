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

.PHONY: all localecompile localegen
