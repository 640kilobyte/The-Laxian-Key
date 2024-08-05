# контейнер базы данных - мастер
FROM postgres:16-bookworm
COPY do_manual /do_manual
COPY app /app
COPY initdb.d/* /docker-entrypoint-initdb.d/
ARG config_file=/app/postgresql.conf