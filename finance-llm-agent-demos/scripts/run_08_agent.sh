#!/usr/bin/env bash
set -euo pipefail

# 08 使用直连 DeepSeek、DuckDuckGo 和新闻站点，不读取本机代理配置。
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

cd "$(dirname "$0")/../08-ai_startup_trend_analysis_agent"
streamlit run startup_trends_agent.py --server.address 127.0.0.1 --server.port 8508
