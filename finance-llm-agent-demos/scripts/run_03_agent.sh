#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../03-ai_personal_finance_agent"
streamlit run finance_agent.py
