#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../06-ai_financial_coach_agent"
streamlit run ai_financial_coach_agent.py
