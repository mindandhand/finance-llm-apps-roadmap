#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../11-agentic_typed_rag_pydanticai"
python3 -m streamlit run app.py
