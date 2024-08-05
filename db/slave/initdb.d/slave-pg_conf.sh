#!/bin/bash
# добавляем пользователя
if [ -z "$POSTGRES_REPL_USER" ]; then
	echo "Fatal: env POSTGRES_REPL_USER not set"
	exit 1
fi

if [ -z "$POSTGRES_REPL_PASSWORD" ]; then
	echo "Fatal: env OSTGRES_REPL_PASSWORD not set"
	exit 1
fi

[ -z "$POSTGRES_USER" ] && POSTGRES_USER=postgres
[ -z "$POSTGRES_DB" ] && $POSTGRES_DB=postgres

# сохранение pg_hba
cp /var/lib/postgresql/data/pg_hba.conf /etc/postgresql