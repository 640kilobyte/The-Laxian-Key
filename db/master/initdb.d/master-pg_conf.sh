#!/bin/bash
#!/bin/bash
set -e

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

# создание пользователя для репликации
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" $POSTGRES_DB <<-EOSQL
	CREATE USER $POSTGRES_REPL_USER WITH REPLICATION PASSWORD '$POSTGRES_REPL_PASSWORD';
EOSQL

cat /app/postgresql.conf > /var/lib/postgresql/data/postgresql.conf

# Конфигурация БД
cat >> /var/lib/postgresql/data/pg_hba.conf << EOF
host replication $POSTGRES_REPL_USER 172.31.255.0/24 scram-sha-256
EOF