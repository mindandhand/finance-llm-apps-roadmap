#!/usr/bin/env bash

QLIB_DEFAULT_INSTRUMENTS="sh510050,sh510300,sh510500,sz159915,sh588000"
export QLIB_INSTRUMENTS="${QLIB_INSTRUMENTS-$QLIB_DEFAULT_INSTRUMENTS}"

# 所有入口统一使用显式解释器、项目虚拟环境或系统 python3。
QLIB_DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${QLIB_PYTHON:-}" ]]; then
  if [[ -x "$QLIB_DEMO_ROOT/.venv/bin/python" ]]; then
    QLIB_PYTHON="$QLIB_DEMO_ROOT/.venv/bin/python"
  else
    QLIB_PYTHON="$(command -v python3 || true)"
  fi
fi
if [[ -z "$QLIB_PYTHON" ]]; then
  echo "Python unavailable; create .venv as described in README.md" >&2
  return 1
fi
export QLIB_PYTHON

# Qlib Recorder 使用本地 MLflow 文件存储；训练示例也会隐式记录指标。
export MLFLOW_ALLOW_FILE_STORE="${MLFLOW_ALLOW_FILE_STORE:-true}"
