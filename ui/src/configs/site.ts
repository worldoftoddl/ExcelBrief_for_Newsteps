export const siteConfig = {
  meta: {
    title: "ExcelBrief for Newsteps",
    description:
      "신입 회계사를 위한 감사조서(Excel) 해설 에이전트 — 조서를 읽고, 수행된 절차를 감사기준·K-IFRS 근거와 함께 설명합니다.",
    favicon: "", // 빈값이면 logoPath 사용
  },
  branding: {
    appName: "ExcelBrief for Newsteps",
    logoPath: "/logo.png",
    logoWidth: 28,
    logoHeight: 28,
    description:
      "신입 회계사를 위한 감사조서(Excel) 해설 에이전트 — 조서를 읽고, 수행된 절차를 감사기준·K-IFRS 근거와 함께 설명합니다.",
  },
  buttons: {
    enableFileUpload: true,
    fileUploadMode: "base64" as const,
    chatInputPlaceholder:
      "조서나 감사기준에 대해 물어보세요. (예: 3650 조서는 어떤 절차를 위한 서식이야?)",
  },
  threads: {
    showHistory: true,
    enableDeletion: true,
    enableTitleEdit: true,
    sidebarOpenByDefault: true,
  },
  theme: {
    fontFamily: "sans" as const,
    fontSize: "medium" as const,
    colorScheme: "light" as const,
  },
  ui: {
    autoCollapseToolCalls: false,
    chatWidth: "default" as const,
    chatHistoryOpen: false,
    tracingPanelOpen: false,
  },
} as const;

/** 프로젝트 저장소 — 헤더 GitHub 버튼이 가리키는 곳 */
export const REPO_URL =
  "https://github.com/worldoftoddl/ExcelBrief_for_Newsteps";

/** 첫 화면 예시 질문 — 데모 조서(가상)와 한공회 공식 서식 기준 */
export const CHAT_STARTERS = [
  "지금 볼 수 있는 감사조서 파일 목록을 보여줘.",
  "데모조서 5300 현금및현금성자산 조서를 해석해줘. 어떤 감사절차가 수행됐어?",
  "작성중인 데모조서 5400 매출채권 조서에 어떤 절차가 추가로 필요한지 알려줘.",
  "'데모_부서별 예산집행 현황' 파일이 뭔지 설명해줘.",
  "3900 핵심감사사항 조서에는 무엇을 채워야 해? 감사기준서 근거와 함께 알려줘.",
  "K-IFRS 1115호 수익 인식 5단계 모형의 근거 문단을 인용해서 설명해줘.",
] as const;
