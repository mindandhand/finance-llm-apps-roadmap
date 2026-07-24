#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../12-ai_financial_data_analysis_agent"
streamlit run app.py
