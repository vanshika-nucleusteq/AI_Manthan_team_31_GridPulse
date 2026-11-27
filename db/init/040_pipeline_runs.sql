-- One row per (run_id, task), written by gridpulse.cli after every step (a retry overwrites it).
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id      TEXT           NOT NULL,
    task        TEXT           NOT NULL,
    ds          DATE           NOT NULL,
    started_at  TIMESTAMPTZ    NOT NULL,
    finished_at TIMESTAMPTZ    NOT NULL,
    duration_s  NUMERIC(10, 2) NOT NULL,
    status      TEXT           NOT NULL CHECK (status IN ('success', 'failed')),
    rows_in     BIGINT,
    rows_out    BIGINT,
    duplicates  BIGINT,
    details     JSONB          NOT NULL DEFAULT '{}',
    PRIMARY KEY (run_id, task)
);
CREATE INDEX IF NOT EXISTS pipeline_runs_ds_idx ON pipeline_runs (ds);
