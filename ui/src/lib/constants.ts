/**
 * Application-wide constants
 * Centralized location for magic numbers and strings
 */

/**
 * UI Layout Constants
 */
export const UI = {
  /** Width of the chat history sidebar in pixels */
  CHAT_SIDEBAR_WIDTH: 300,
  /** Width of the tracing sidebar in pixels */
  TRACING_SIDEBAR_WIDTH: 400,
  /** Maximum height of the chat textarea in pixels */
  CHAT_TEXTAREA_MAX_HEIGHT: 490,
  /** Logo scale factor for splash screen */
  LOGO_SCALE_FACTOR: 1.5,
  /** Maximum length for tool result truncation */
  MAX_TOOL_RESULT_LENGTH: 100,
  /** Maximum height for TODO box in pixels */
  TODO_BOX_MAX_HEIGHT: 300,
} as const;

/**
 * Timing Constants
 */
export const TIMING = {
  /** Delay before fetching threads after creation (milliseconds) */
  THREAD_FETCH_DELAY: 4000,
  /** Polling interval for LangSmith runs (milliseconds) */
  POLLING_INTERVAL: 5000,
  /** Delay before refetching LangSmith data after streaming ends */
  LANGSMITH_REFETCH_DELAY: 2000,
  /** Default animation duration (milliseconds) */
  ANIMATION_DURATION: 300,
} as const;

/**
 * Stream configuration options
 * Used for consistent streaming behavior across components
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const STREAM_OPTIONS: any = {
  // messages-tuple: LLM 토큰 스트리밍 — 최종 노드(agent 답변·chat 노드)의
  // 답변이 토큰 단위로 흐른다. 중간 노드 토큰은 MessageList의
  // isIntermediateNodeMessage가 streamMetadata.langgraph_node로 걸러낸다.
  streamMode: ["values", "updates", "custom", "messages-tuple"],
  streamSubgraphs: true,
  streamResumable: true,
};

/**
 * Cookie Constants
 */
export const COOKIES = {
  /** Default cookie max age: 1 year (seconds) */
  MAX_AGE: 60 * 60 * 24 * 365,
} as const;

/**
 * Placeholder text for chat input
 * Use t('placeholder') from useTranslations('chat') in components instead
 */
