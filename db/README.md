# Настройка

Требуется ручная настройка репликации:

```bash
docker exec -it the-laxian-key-db_slave-1 /do_manual/setup_db_replication.sh
docker start the-laxian-key-db_slave-1
```

Проверка:

```bash
docker exec -it the-laxian-key-db_main-1  psql --username postgres -c 'select * from pg_stat_replication;'
docker exec -it the-laxian-key-db_slave-1 psql --username postgres -c 'select * from pg_stat_wal_receiver;'
```

И инициализация данных:

```bash
docker exec -it the-laxian-key-db_main-1 /do_manual/init_bot_database.sh
```