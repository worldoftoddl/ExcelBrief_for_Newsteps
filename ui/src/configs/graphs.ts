import { siteConfig, CHAT_STARTERS } from "./site";

export interface GraphMeta {
  /** 그래프 셀렉터에 표시되는 이름 */
  displayName: string;
  /** 첫 화면(WelcomeScreen) 소개문 */
  description: string;
  /** 첫 화면 예시 질문 */
  starters: readonly string[];
}

/**
 * graph_id → 그래프별 메타.
 * langgraph 서버가 자동 생성하는 assistant의 name은 graph_id 그대로라
 * (컨테이너 재시작 시 초기화되므로 서버 쪽 rename은 유지되지 않음)
 * 표시명·소개·예시 질문을 UI에서 매핑한다. 목록에 없는 graph_id는
 * siteConfig 기본값으로 렌더된다.
 */
export const GRAPH_META: Record<string, GraphMeta> = {
  agent: {
    displayName: "조서와 대화하기",
    description:
      "조서 읽기·표 SQL·기준서 검색·웹 검색·웹 추출 도구를 모두 쥔 범용 ReAct 에이전트 — " +
      "여러 파일을 넘나드는 질문이나 기준서 자체 질문은 여기서 하세요.",
    starters: CHAT_STARTERS,
  },
  analyst: {
    displayName: "대형 엑셀 분석 Agent",
    description:
      "대형 Excel·CSV 표를 격리된 읽기 전용 SQL로 집계·분석합니다 — " +
      "분석할 파일을 첨부하거나 파일명을 언급해 질문하세요.",
    starters: [
      "매출시트_데모.csv에서 도시별 매출 합계와 평균 평점을 구해줘.",
      "매출시트_데모.csv에서 매출이 가장 큰 도시의 제품라인별 매출 순위를 보여줘.",
      "매출시트_데모.csv에서 결제수단별 거래 건수와 매출 비중을 계산해줘.",
      "'데모_부서별 예산집행 현황' 파일에서 부서별 집행률을 계산해줘.",
    ],
  },
  profiler: {
    displayName: "기업이해 Agent",
    description:
      "감사 착수 전에 확보해야 할 회사 이해를 공개 웹 자료로 브리핑합니다 — " +
      "산업·사업·재무·최근 이슈와 유의적 위험 후보까지. 회사명이나 조사할 URL을 알려주세요.",
    starters: [
      "https://ko.wikipedia.org/wiki/네이버 자료를 바탕으로 네이버 기업이해 브리핑을 만들어줘.",
      "삼성전자에 대해 감사 착수 전 기업이해 브리핑을 만들어줘.",
      "카카오의 최근 이슈와 유의적 위험 후보를 정리해줘.",
    ],
  },
};

/**
 * UI에서 숨기는 graph_id — 서버에는 등록돼 있지만 셀렉터에 노출하지 않는다.
 * (explainer·reviewer의 역할은 agent가 대체)
 */
export const HIDDEN_GRAPH_IDS: readonly string[] = ["explainer", "reviewer"];
