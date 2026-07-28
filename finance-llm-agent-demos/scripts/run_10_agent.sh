#!/usr/bin/env bash
set -euo pipefail

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

cd "$(dirname "$0")/../10-rag_failure_diagnostics_clinic"
python rag_failure_diagnostics_clinic.py
