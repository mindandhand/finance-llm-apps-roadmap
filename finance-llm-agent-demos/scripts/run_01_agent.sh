#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../01-ai_finance_agent"
python finance_agent.py
