#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../04-ai_finance_agent_team"
python finance_agent_team.py
