#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../16-local_hybrid_financial_rag"
streamlit run app.py
