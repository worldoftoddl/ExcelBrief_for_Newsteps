#!/usr/bin/env bash
# 단일 컨테이너 기동: langgraph 서버(:2024) → 준비 확인 → Next UI(:7860)
set -euo pipefail

python -m langgraph_cli dev --no-browser --host 0.0.0.0 --port 2024 &

# 백엔드 준비 대기 (최대 120초) — 첫 부팅은 그래프 로드로 수십 초 걸릴 수 있음
python - <<'EOF'
import time
import urllib.request

for i in range(120):
    try:
        urllib.request.urlopen("http://127.0.0.1:2024/info", timeout=2)
        print(f"langgraph 서버 준비 완료 ({i + 1}초)", flush=True)
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("langgraph 서버가 120초 내에 준비되지 않음")
EOF

# credentials 모드: 시드 계정 upsert (Space 파일시스템은 휘발성 — 매 기동마다)
if [ "${AUTH_MODE:-standalone}" = "credentials" ] && [ -n "${DATABASE_URL:-}" ]; then
    (cd ui && node scripts/seed-users.mjs)
fi

exec node ui/server.js
