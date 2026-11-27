-- Anomaly events from gridpulse.anomalies (spike, tamper, outage); published like the gold tables.
CREATE TABLE IF NOT EXISTS anomalies (
    anomaly_id   TEXT           PRIMARY KEY,
    type         TEXT           NOT NULL CHECK (type IN ('spike', 'tamper', 'outage')),
    meter_id     TEXT,
    feeder_id    TEXT           NOT NULL,
    zone_id      TEXT           NOT NULL,
    local_date   DATE           NOT NULL,
    window_start TIMESTAMPTZ    NOT NULL,
    window_end   TIMESTAMPTZ    NOT NULL,
    score        NUMERIC(12, 4) NOT NULL,
    details      JSONB          NOT NULL
);
CREATE INDEX IF NOT EXISTS anomalies_date_idx ON anomalies (local_date);
CREATE INDEX IF NOT EXISTS anomalies_type_idx ON anomalies (type, local_date);
