#!/bin/bash
set -e

if [ -z "$POSTGRES_REPL_USER" ]; then
	echo "Fatal: env POSTGRES_REPL_USER not set"
	exit 1
fi

if [ -z "$POSTGRES_REPL_PASSWORD" ]; then
	echo "Fatal: env POSTGRES_REPL_PASSWORD not set"
	exit 1
fi

rm -rfv /var/lib/postgresql/data/*
PGPASSWORD="$POSTGRES_REPL_PASSWORD" pg_basebackup -R -h db_main -U "$POSTGRES_REPL_USER" -D /var/lib/postgresql/data -P