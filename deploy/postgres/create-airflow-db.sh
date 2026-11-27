#!/bin/sh
# Runs once, on an empty pgdata volume: create the Airflow metadata database next to POSTGRES_DB.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "CREATE DATABASE \"${AIRFLOW_DB:-airflow}\" OWNER \"$POSTGRES_USER\""
