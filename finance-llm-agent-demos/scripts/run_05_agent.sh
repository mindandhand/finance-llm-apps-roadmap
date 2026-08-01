#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../05-ai_life_insurance_advisor_agent"
streamlit run life_insurance_advisor_agent.py
