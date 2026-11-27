-- Gold tables published from the lake by gridpulse.publish.postgres (delete-then-insert per date).
-- Columns match src/gridpulse/aggregate/tables.py. kWh is NUMERIC(18,6); times are TIMESTAMPTZ (UTC).
CREATE TABLE IF NOT EXISTS consumption_hourly (
    meter_id          TEXT          NOT NULL,
    feeder_id         TEXT          NOT NULL,
    zone_id           TEXT          NOT NULL,
    local_date        DATE          NOT NULL,
    hour_start        TIMESTAMPTZ   NOT NULL,
    kwh               NUMERIC(18, 6) NOT NULL,
    intervals_present INTEGER       NOT NULL,
    has_gap           BOOLEAN       NOT NULL,
    PRIMARY KEY (meter_id, hour_start)
);
CREATE INDEX IF NOT EXISTS consumption_hourly_date_idx ON consumption_hourly (local_date);

CREATE TABLE IF NOT EXISTS consumption_hourly_feeder (
    feeder_id         TEXT          NOT NULL,
    zone_id           TEXT          NOT NULL,
    local_date        DATE          NOT NULL,
    hour_start        TIMESTAMPTZ   NOT NULL,
    kwh               NUMERIC(18, 6) NOT NULL,
    meters_reporting  INTEGER       NOT NULL,
    meters_expected   INTEGER       NOT NULL,
    intervals_present INTEGER       NOT NULL,
    completeness_pct  NUMERIC(5, 2) NOT NULL,
    PRIMARY KEY (feeder_id, hour_start)
);
CREATE INDEX IF NOT EXISTS consumption_hourly_feeder_date_idx ON consumption_hourly_feeder (local_date);

CREATE TABLE IF NOT EXISTS consumption_hourly_zone (
    zone_id           TEXT          NOT NULL,
    local_date        DATE          NOT NULL,
    hour_start        TIMESTAMPTZ   NOT NULL,
    kwh               NUMERIC(18, 6) NOT NULL,
    meters_reporting  INTEGER       NOT NULL,
    meters_expected   INTEGER       NOT NULL,
    intervals_present INTEGER       NOT NULL,
    completeness_pct  NUMERIC(5, 2) NOT NULL,
    PRIMARY KEY (zone_id, hour_start)
);
CREATE INDEX IF NOT EXISTS consumption_hourly_zone_date_idx ON consumption_hourly_zone (local_date);

CREATE TABLE IF NOT EXISTS consumption_daily_meter (
    meter_id          TEXT          NOT NULL,
    feeder_id         TEXT          NOT NULL,
    zone_id           TEXT          NOT NULL,
    local_date        DATE          NOT NULL,
    kwh               NUMERIC(18, 6) NOT NULL,
    intervals_present INTEGER       NOT NULL,
    completeness_pct  NUMERIC(5, 2) NOT NULL,
    quality_flag      BOOLEAN       NOT NULL,
    PRIMARY KEY (meter_id, local_date)
);
CREATE INDEX IF NOT EXISTS consumption_daily_meter_date_idx ON consumption_daily_meter (local_date);

CREATE TABLE IF NOT EXISTS consumption_daily_feeder (
    feeder_id         TEXT          NOT NULL,
    zone_id           TEXT          NOT NULL,
    local_date        DATE          NOT NULL,
    kwh               NUMERIC(18, 6) NOT NULL,
    meters_reporting  INTEGER       NOT NULL,
    meters_expected   INTEGER       NOT NULL,
    intervals_present INTEGER       NOT NULL,
    completeness_pct  NUMERIC(5, 2) NOT NULL,
    quality_flag      BOOLEAN       NOT NULL,
    PRIMARY KEY (feeder_id, local_date)
);

CREATE TABLE IF NOT EXISTS consumption_daily_zone (
    zone_id           TEXT          NOT NULL,
    local_date        DATE          NOT NULL,
    kwh               NUMERIC(18, 6) NOT NULL,
    meters_reporting  INTEGER       NOT NULL,
    meters_expected   INTEGER       NOT NULL,
    intervals_present INTEGER       NOT NULL,
    completeness_pct  NUMERIC(5, 2) NOT NULL,
    quality_flag      BOOLEAN       NOT NULL,
    PRIMARY KEY (zone_id, local_date)
);

CREATE TABLE IF NOT EXISTS data_quality_daily (
    local_date        DATE          NOT NULL,
    rule              TEXT          NOT NULL,
    failures          INTEGER       NOT NULL,
    sample_meter_ids  TEXT[]        NOT NULL,
    PRIMARY KEY (local_date, rule)
);

CREATE TABLE IF NOT EXISTS billing_monthly (
    meter_id             TEXT          NOT NULL,
    feeder_id            TEXT          NOT NULL,
    zone_id              TEXT          NOT NULL,
    month                DATE          NOT NULL,
    kwh                  NUMERIC(18, 6) NOT NULL,
    sum_of_intervals_kwh NUMERIC(18, 6) NOT NULL,
    start_reading_source TEXT          NOT NULL CHECK (start_reading_source IN ('previous_month', 'first_in_month')),
    readings             INTEGER       NOT NULL,
    days_flagged         INTEGER       NOT NULL,
    period_complete      BOOLEAN       NOT NULL,
    billing_status       TEXT          NOT NULL CHECK (billing_status IN ('READY', 'REVIEW')),
    PRIMARY KEY (meter_id, month)
);
CREATE INDEX IF NOT EXISTS billing_monthly_month_idx ON billing_monthly (month);
