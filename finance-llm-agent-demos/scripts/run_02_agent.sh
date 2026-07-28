#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../02-ai_investment_agent"
python investment_agent.py
