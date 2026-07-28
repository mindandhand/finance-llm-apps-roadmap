#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../21-finance_dashboard_generator"
streamlit run app.py
