# LandFinder

An agentic land prospecting system for Steven Christie at Keller Williams Real Estate, Chester County PA.

## Overview

LandFinder automates the discovery, outreach, and follow-up workflow for vacant land parcels. It uses AI to prioritize leads, generate personalized letters, and manage multi-channel touchpoints (mail, email, SMS).

## Tech Stack

- **Python** — core application logic
- **Supabase (Postgres)** — database for parcels, letters, touchpoints, and agent configs
- **Streamlit** — agent dashboard UI
- **Anthropic API** — AI-powered scoring, letter generation, and decision making
- **Lob** — direct mail / physical letter sending
- **SendGrid** — email outreach
- **Twilio** — SMS touchpoints
- **BatchLeads** — parcel and owner data sourcing
- **Google Maps Static API** — satellite imagery for parcels
- **GitHub Actions** — scheduled automation workflows

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd landfinder
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

**Required variables:**

| Variable | Where to find it |
|---|---|
| `SUPABASE_URL` | Supabase Dashboard > Settings > API |
| `SUPABASE_KEY` | Supabase Dashboard > Settings > API (anon/public key) |
| `SUPABASE_DB_URL` | Supabase Dashboard > Settings > Database > Connection string (URI mode) |
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `LOB_TEST_KEY` | dashboard.lob.com |
| `LOB_LIVE_KEY` | dashboard.lob.com |
| `SENDGRID_API_KEY` | app.sendgrid.com |
| `TWILIO_SID` | console.twilio.com |
| `TWILIO_TOKEN` | console.twilio.com |
| `TWILIO_PHONE` | Your Twilio phone number |
| `BATCHLEADS_KEY` | app.batchleads.io |
| `GOOGLE_MAPS_KEY` | console.cloud.google.com |

### 3. Initialize the database schema

```bash
python functions/schema_setup.py
```

This creates all tables and seeds initial data for Steven Christie.

### 4. Run tests

```bash
python tests/test_sprint1.py
```

## Project Structure

```
landfinder/
  functions/          # Reusable Python modules
  tests/              # Test scripts
  .github/
    workflows/        # GitHub Actions schedulers
  .env.example        # Environment variable template
  requirements.txt    # Python dependencies
  README.md           # This file
```

## Database Schema

- **parcels** — land parcel leads with owner info, status, and scoring
- **letters** — outgoing mail pieces tracked via Lob
- **touchpoints** — all outreach events across channels
- **agent_decisions** — AI reasoning log for each parcel action
- **agent_configs** — per-agent settings, criteria, and preferences

## Agent

- **Agent ID:** `steven_christie`
- **Brokerage:** Keller Williams Real Estate
- **Target Area:** Chester County, PA
- **Lot Size Range:** 1–50 acres
- **Price Range:** $50,000–$2,000,000
