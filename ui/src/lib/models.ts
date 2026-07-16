/**
 * 모델 레지스트리 — 에이전트의 resolve_model(src/agent/graph.py) 접두사 라우팅과
 * 짝을 이룬다. /api/models 라우트가 envKey 존재 여부로 필터해 클라이언트에
 * 노출하므로, 벤더 API 키가 없는 모델은 드롭다운에 나타나지 않는다.
 */

export interface ModelOption {
  /** resolve_model에 그대로 전달되는 스펙 (예: "anthropic:claude-sonnet-5") */
  spec: string;
  label: string;
  provider: string;
}

export interface RegisteredModel extends ModelOption {
  /** 이 환경변수 중 하나라도 설정된 경우에만 노출 */
  envKeys: string[];
}

export const MODEL_REGISTRY: RegisteredModel[] = [
  {
    spec: "anthropic:claude-sonnet-5",
    label: "Claude Sonnet 5 (기본)",
    provider: "Anthropic",
    envKeys: ["ANTHROPIC_API_KEY"],
  },
  {
    spec: "anthropic:claude-haiku-4-5-20251001",
    label: "Claude Haiku 4.5 (빠름)",
    provider: "Anthropic",
    envKeys: ["ANTHROPIC_API_KEY"],
  },
  {
    spec: "openai:gpt-5.1",
    label: "GPT-5.1",
    provider: "OpenAI",
    envKeys: ["OPENAI_API_KEY"],
  },
  {
    spec: "openai:gpt-5-mini",
    label: "GPT-5 mini (빠름)",
    provider: "OpenAI",
    envKeys: ["OPENAI_API_KEY"],
  },
  // Gemini는 -latest 별칭 사용 — 세대 교체(2.5 지원 종료 실측)에도 깨지지 않음
  {
    spec: "google_genai:gemini-pro-latest",
    label: "Gemini Pro (최신)",
    provider: "Google",
    envKeys: ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
  },
  {
    spec: "google_genai:gemini-flash-latest",
    label: "Gemini Flash (빠름)",
    provider: "Google",
    envKeys: ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
  },
  // HF Inference Providers 라우터 — 오픈모델 서버리스 (GPU Space 불필요)
  {
    spec: "hf:Qwen/Qwen3.6-27B",
    label: "Qwen3.6 27B (오픈모델·HF)",
    provider: "HuggingFace",
    envKeys: ["HF_INFERENCE_TOKEN"],
  },
  {
    spec: "hf:openai/gpt-oss-120b",
    label: "gpt-oss 120B (오픈모델·HF)",
    provider: "HuggingFace",
    envKeys: ["HF_INFERENCE_TOKEN"],
  },
  {
    spec: "local:qwen3:8b-16k",
    label: "Qwen3 8B (로컬 Ollama)",
    provider: "Local",
    envKeys: ["LOCAL_LLM_BASE_URL"],
  },
];

export const DEFAULT_MODEL_SPEC = "anthropic:claude-sonnet-5";

export const MODEL_STORAGE_KEY = "excelbrief:model";

/** 사용 가능 모델 목록을 서버에서 받아온다. 실패 시 빈 배열. */
export async function fetchAvailableModels(): Promise<ModelOption[]> {
  try {
    const res = await fetch("/api/models");
    if (!res.ok) return [];
    const body = (await res.json()) as { models?: ModelOption[] };
    return body.models ?? [];
  } catch {
    return [];
  }
}

/** 마지막 선택 모델. submit 시점마다 읽으므로 상태를 컴포넌트 간에 돌릴 필요가 없다. */
export function getStoredModelSpec(): string {
  if (typeof window === "undefined") return DEFAULT_MODEL_SPEC;
  return window.localStorage.getItem(MODEL_STORAGE_KEY) ?? DEFAULT_MODEL_SPEC;
}

export function storeModelSpec(spec: string): void {
  try {
    window.localStorage.setItem(MODEL_STORAGE_KEY, spec);
  } catch {
    // localStorage 비활성 환경(시크릿 모드 등)에서는 세션 한정 선택으로 동작
  }
}

/** stream.submit options.config에 그대로 넣는 런 설정 — 모든 submit 지점 공통. */
export function modelRunConfig(): { configurable: { model: string } } {
  return { configurable: { model: getStoredModelSpec() } };
}
