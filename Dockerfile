# ExcelBrief for Newsteps — HuggingFace Space 단일 컨테이너
#
# 구성: langgraph 서버(내부 :2024) + Next.js UI(:7860, HF 노출 포트).
# 브라우저는 Space 도메인의 /api 로 접속하고 Next 서버가 :2024 로 중계한다
# (API passthrough — 로컬 WSL2에서 검증한 구성과 동일).
#
# Space 시크릿(Settings → Variables and secrets):
#   ANTHROPIC_API_KEY, MCP_AUTH_TOKEN, LANGSMITH_API_KEY (선택: LANGSMITH_TRACING=true)

# ── Stage 1: UI 빌드 ─────────────────────────────────────────────────────
FROM node:24-slim AS ui-builder
WORKDIR /build/ui
RUN corepack enable
COPY ui/package.json ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY ui/ ./
# NEXT_PUBLIC_* 는 빌드타임에 번들로 인라인된다. /api 는 상대 경로 —
# normalizeApiUrl이 window.location.origin과 결합하므로 어떤 도메인에서든 동작.
ENV NEXT_PUBLIC_API_URL=/api \
    NEXT_PUBLIC_ASSISTANT_ID=agent
RUN pnpm build

# ── Stage 2: 런타임 (Python + Node) ──────────────────────────────────────
FROM python:3.12-slim
# standalone server.js 실행에는 node 바이너리 하나면 충분 (npm 불필요).
# node:24-slim도 Debian(glibc)이라 바이너리 호환.
COPY --from=node:24-slim /usr/local/bin/node /usr/local/bin/node

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

COPY --chown=user requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir --user -r requirements.lock

COPY --chown=user src/ src/
RUN pip install --no-cache-dir --user --no-deps .

COPY --chown=user langgraph.json start.sh ./
COPY --chown=user data/workpapers/ data/workpapers/
COPY --from=ui-builder --chown=user /build/ui/.next/standalone ui/
COPY --from=ui-builder --chown=user /build/ui/.next/static ui/.next/static
COPY --from=ui-builder --chown=user /build/ui/public ui/public

# langgraph.json이 "env": "./.env"를 참조하므로 빈 파일을 둔다 —
# 실제 설정은 Space 시크릿이 환경변수로 주입한다.
RUN touch .env

ENV WORKPAPERS_DIR=/home/user/app/data/workpapers \
    MCP_TRANSPORT=http \
    MCP_HTTP_URL=https://toddl-auditpaper-mcp.hf.space/mcp \
    LANGSMITH_PROJECT=excelbrief \
    LANGGRAPH_API_URL=http://127.0.0.1:2024 \
    PORT=7860 \
    HOSTNAME=0.0.0.0

EXPOSE 7860
CMD ["bash", "start.sh"]
