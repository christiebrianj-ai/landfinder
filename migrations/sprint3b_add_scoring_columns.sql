-- LandFinder Sprint 3B migration: parcel opportunity scoring columns
-- Paste into: Supabase Dashboard > SQL Editor > New Query > Run

ALTER TABLE parcels ADD COLUMN IF NOT EXISTS opportunity_score FLOAT DEFAULT 0;
ALTER TABLE parcels ADD COLUMN IF NOT EXISTS score_reasoning TEXT;
ALTER TABLE parcels ADD COLUMN IF NOT EXISTS scored_at TIMESTAMPTZ;
