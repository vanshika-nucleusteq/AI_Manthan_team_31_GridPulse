-- Meter master: one row per synthetic meter, seeded from data/meter_master.csv by gridpulse.publish.init_db.
CREATE TABLE IF NOT EXISTS meter_master (
    meter_id         TEXT          PRIMARY KEY CHECK (meter_id ~ '^MTR-[0-9]{5}$'),
    feeder_id        TEXT          NOT NULL CHECK (feeder_id ~ '^F[0-9]{2}$'),
    zone_id          TEXT          NOT NULL CHECK (zone_id ~ '^Z[0-9]+$'),
    meter_type       TEXT          NOT NULL CHECK (meter_type IN ('residential', 'commercial')),
    reporting_unit   TEXT          NOT NULL CHECK (reporting_unit IN ('Wh', 'kWh')),
    register_max_kwh NUMERIC(18, 6) NOT NULL CHECK (register_max_kwh > 0),
    install_date     DATE          NOT NULL,
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS meter_master_feeder_idx ON meter_master (feeder_id);
CREATE INDEX IF NOT EXISTS meter_master_zone_idx ON meter_master (zone_id);
