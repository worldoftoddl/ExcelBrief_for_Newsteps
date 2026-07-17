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
    displayName: "조서 해설 Agent",
    description: siteConfig.branding.description,
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
  reviewer: {
    displayName: "조서 검토 Agent",
    description:
      "작성 중인 감사조서의 완성도를 점검합니다 — 절차 누락, 서명란 공란, " +
      "검산(tie-out) 이상을 찾아 보고서로 정리합니다.",
    starters: [
      "작성중인 데모조서 5400 매출채권 조서를 검토해줘.",
      "데모조서 5300 현금및현금성자산 조서의 완성도를 점검해줘.",
      "감사조서서식_2700A 중요성요약표에 채워야 할 항목이 남았는지 검토해줘.",
    ],
  },
};
