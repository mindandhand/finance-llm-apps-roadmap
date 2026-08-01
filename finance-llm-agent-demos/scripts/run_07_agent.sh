#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../07-ai_vc_due_diligence_agent_team"
python agent.py
