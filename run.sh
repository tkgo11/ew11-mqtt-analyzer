#!/usr/bin/env bash
# EW11 MQTT 패킷 분석기 실행 스크립트
# 사용법:
#   ./run.sh --demo                      데모 모드 (월패드 없이 체험)
#   ./run.sh --host 192.168.x.x          실제 MQTT 브로커 연결
#   ./run.sh --host 192.168.x.x --port 1883 --topic "ew11/#"
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "venv가 없습니다. 생성합니다..."
  python3 -m venv .venv
  ./.venv/bin/pip install -e '.[dev]'
fi

if [ ! -d frontend/dist ]; then
  echo "프론트엔드 빌드가 없습니다. 빌드합니다..."
  (cd frontend && npm ci && npm run build)
fi

exec ./.venv/bin/python -m ew11_analyzer "$@"
