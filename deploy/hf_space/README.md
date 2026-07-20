---
title: Agent for Newstep
emoji: 📊
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Agent for Newstep

회계법인 신입(뉴스텝) 회계사를 위한 감사조서 Excel 해설 에이전트.
조서를 읽고 한국 회계감사기준·K-IFRS·회계감사실무지침에 근거해
수행된 감사절차를 해석하고, 미완성 조서에는 추가 필요 절차를 제안한다.
코드·문서는 [GitHub 저장소](https://github.com/worldoftoddl/Agent_for_Newstep) 참조.

이 Space는 위 저장소를 빌드 시 clone해 langgraph 서버(내부 :2024)와
Next.js 채팅 UI(:7860)를 한 컨테이너에서 실행한다. 브라우저는 Space
도메인의 `/api`로 접속하고 Next 서버가 내부 백엔드로 중계한다.

번들된 데이터는 전부 **가상 샘플 조서**와 한공회 공식 빈 서식이다 —
실제 피감사회사 데이터는 포함하지 않는다.

## Space 운영자 설정 (Settings → Variables and secrets)

| Secret | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API 키 (기본 모델 라우트) |
| `MCP_AUTH_TOKEN` | auditpaper-mcp Space의 Bearer 토큰 (기준서 RAG) |
| `NEXTAUTH_SECRET` | NextAuth 세션 서명 키 (`openssl rand -base64 32`) |
| `SEED_USER_EMAIL` | 로그인 허용 시드 계정 이메일 (기동 시 자동 생성) |
| `SEED_USER_PASSWORD` | 시드 계정 비밀번호 (교체 = 시크릿 변경 후 재시작) |
| `LANGSMITH_API_KEY` | (선택) LangSmith 트레이싱 키 |
| `LANGSMITH_TRACING` | (선택) `true` — 트레이싱 활성화 시 Variables에 |

- **접근 제어**: `AUTH_MODE=credentials` — 시드 계정만 로그인 가능하다.
  자가 가입은 승인 대기(pending)로 잠기며 승인 주체를 두지 않는다.
  로그인 세션 쿠키는 cross-site iframe 대응(None+Secure)이지만, 브라우저가
  서드파티 쿠키를 차단하면 iframe 로그인이 실패할 수 있다 — 그 경우
  직접 URL(`https://toddl-excelbrief.hf.space`)로 안내할 것.

- 기준서 RAG는 [toddl/auditpaper-mcp](https://huggingface.co/spaces/toddl/auditpaper-mcp)
  Space를 HTTP MCP로 호출한다 (`MCP_HTTP_URL`은 Dockerfile 기본값).
  연결 실패 시에도 에이전트는 기준 인용 없이 동작한다.
- GitHub 저장소의 코드가 갱신되면 **Settings → Factory rebuild**로 재배포.
