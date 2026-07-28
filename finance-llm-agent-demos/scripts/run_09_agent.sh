#!/usr/bin/env bash
set -euo pipefail

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

cd "$(dirname "$0")/../09-deepseek_local_rag_agent"
streamlit run deepseek_rag_agent.py --server.address 127.0.0.1 --server.port 8509
