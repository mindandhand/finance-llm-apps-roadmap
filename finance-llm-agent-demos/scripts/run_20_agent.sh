#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../20-insurance_claim_text_agent_team"
streamlit run app.py
