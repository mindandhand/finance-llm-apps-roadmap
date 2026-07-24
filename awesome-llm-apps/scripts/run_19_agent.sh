#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../19-market_event_radar_agent"
streamlit run app.py
