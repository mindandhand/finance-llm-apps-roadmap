#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../15-finance_mcp_agent_router"
streamlit run app.py
