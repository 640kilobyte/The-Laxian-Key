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

[ -z "$POSTGRES_USER" ] && POSTGRES_USER=postgres
[ -z "$POSTGRES_DB" ] && POSTGRES_DB=postgres

if [ -z "DB_USER" ]; then
	echo "Fatal: env DB_USER not set"
	exit 1
fi

if [ -z "DB_PASS" ]; then
	echo "Fatal: env DB_PASS not set"
	exit 1
fi

if [ -z "DB_DTBS" ]; then
	echo "Fatal: env DDB_DTBSB_PASS not set"
	exit 1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" $POSTGRES_DB <<-EOSQL
	CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';
	CREATE DATABASE $DB_DTBS;
	GRANT ALL PRIVILEGES ON database $DB_DTBS to $DB_USER;
	ALTER DATABASE $DB_DTBS OWNER to $DB_USER;
EOSQL