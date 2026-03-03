-- LandFinder — Sprint 1 Schema Setup
-- Paste this entire file into:
--   Supabase Dashboard > SQL Editor > New Query > Run

-- ─────────────────────────────────────────────
-- TABLES
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS parcels (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address               TEXT,
    city                  TEXT,
    state                 TEXT,
    zip                   TEXT,
    county                TEXT,
    township              TEXT,
    lot_size_acres        FLOAT,
    list_price            FLOAT,
    days_on_market        INT,
    mls_id                TEXT,
    owner_name            TEXT,
    owner_mailing_address TEXT,
    owner_phone           TEXT,
    owner_email           TEXT,
    satellite_image_url   TEXT,
    status                TEXT DEFAULT 'new',
    parcel_notes          TEXT,
    agent_priority_score  FLOAT,
    agent_id              TEXT DEFAULT 'steven_christie',
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at           TIMESTAMPTZ,
    letter_sent_at        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS letters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id       UUID REFERENCES parcels(id),
    owner_name      TEXT,
    mailing_address TEXT,
    letter_body     TEXT,
    lob_letter_id   TEXT,
    status          TEXT DEFAULT 'draft',
    send_date       DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS touchpoints (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id         UUID REFERENCES parcels(id),
    channel           TEXT,
    content           TEXT,
    sent_at           TIMESTAMPTZ DEFAULT NOW(),
    response_received BOOLEAN DEFAULT FALSE,
    response_notes    TEXT,
    touch_number      INT
);

CREATE TABLE IF NOT EXISTS agent_decisions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id   UUID REFERENCES parcels(id),
    action      TEXT,
    reasoning   TEXT,
    decided_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_configs (
    agent_id              TEXT PRIMARY KEY,
    agent_name            TEXT,
    agent_email           TEXT,
    agent_phone           TEXT,
    brokerage             TEXT,
    target_counties       TEXT[],
    min_lot_size_acres    FLOAT,
    max_lot_size_acres    FLOAT,
    min_price             FLOAT,
    max_price             FLOAT,
    max_days_on_market    INT,
    active_channels       TEXT[],
    retouch_cadence_days  INT,
    sample_letters        TEXT[],
    sendgrid_from_email   TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- SEED: agent_configs
-- ─────────────────────────────────────────────

INSERT INTO agent_configs (
    agent_id, agent_name, agent_email, agent_phone, brokerage,
    target_counties, min_lot_size_acres, max_lot_size_acres,
    min_price, max_price, max_days_on_market,
    active_channels, retouch_cadence_days, sample_letters,
    sendgrid_from_email
) VALUES (
    'steven_christie',
    'Steven Christie',
    'stevenchristie4@gmail.com',
    '610-389-2810',
    'Keller Williams Real Estate',
    ARRAY['Chester'],
    1.0,
    50.0,
    50000,
    2000000,
    180,
    ARRAY['mail', 'email', 'sms'],
    28,
    ARRAY[]::TEXT[],
    'stevenchristie4@gmail.com'
)
ON CONFLICT (agent_id) DO UPDATE SET
    agent_name           = EXCLUDED.agent_name,
    agent_email          = EXCLUDED.agent_email,
    agent_phone          = EXCLUDED.agent_phone,
    brokerage            = EXCLUDED.brokerage,
    target_counties      = EXCLUDED.target_counties,
    min_lot_size_acres   = EXCLUDED.min_lot_size_acres,
    max_lot_size_acres   = EXCLUDED.max_lot_size_acres,
    min_price            = EXCLUDED.min_price,
    max_price            = EXCLUDED.max_price,
    max_days_on_market   = EXCLUDED.max_days_on_market,
    active_channels      = EXCLUDED.active_channels,
    retouch_cadence_days = EXCLUDED.retouch_cadence_days,
    sendgrid_from_email  = EXCLUDED.sendgrid_from_email;

-- ─────────────────────────────────────────────
-- SEED: parcels (test row)
-- ─────────────────────────────────────────────

INSERT INTO parcels (
    address, city, state, zip, county, township,
    lot_size_acres, list_price, days_on_market, mls_id,
    owner_name, owner_mailing_address, status, agent_id
)
SELECT
    '123 Test Farm Rd', 'West Chester', 'PA', '19382',
    'Chester', 'Birmingham',
    5.2, 250000, 45, 'MLS123456',
    'John Test', '456 Owner St, Philadelphia PA 19103',
    'new', 'steven_christie'
WHERE NOT EXISTS (
    SELECT 1 FROM parcels WHERE mls_id = 'MLS123456'
);
