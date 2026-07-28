#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../18-financial_research_workspace"
streamlit run app.py
