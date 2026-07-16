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
# openssl: prisma generate가 엔진 검증에 사용 (standalone 모드여도 빌드에는 필요)
RUN corepack enable \
    && apt-get update \
    && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY ui/package.json ui/pnpm-lock.yaml ./
# postinstall(prisma generate)은 아직 없는 scripts/·prisma/를 참조하므로 건너뛴다
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY ui/ ./
# NEXT_PUBLIC_* 는 빌드타임에 번들로 인라인된다. 클라이언트는 항상
# window.location.origin + /api 로 호출(normalizeApiUrl)하므로 도메인 무관.
# AUTH_MODE=standalone: 인증·DB 없이 단일 사용자 모드.
ENV NEXT_PUBLIC_API_URL=/api \
    NEXT_PUBLIC_ASSISTANT_ID=agent \
    AUTH_MODE=standalone \
    NEXT_PUBLIC_AUTH_MODE=standalone \
    NEXT_PUBLIC_DEFAULT_LOCALE=ko \
    DATABASE_PROVIDER=sqlite
# build 스크립트가 prisma generate → next build 순으로 실행
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
    AUTH_MODE=standalone \
    NEXT_PUBLIC_AUTH_MODE=standalone \
    NEXT_PUBLIC_DEFAULT_LOCALE=ko \
    PORT=7860 \
    HOSTNAME=0.0.0.0

EXPOSE 7860
CMD ["bash", "start.sh"]
