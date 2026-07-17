import { RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Assistant } from "@/app/actions/assistant";
import { useTranslations } from "next-intl";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";

interface AssistantSelectorProps {
  assistants: Assistant[];
  selectedAssistantId?: string;
  isLoading: boolean;
  onSelect: (assistantId: string) => void;
  onRefresh: () => void;
}

/**
 * graph_id → 한국어 표시명.
 * langgraph 서버가 자동 생성하는 assistant의 name은 graph_id 그대로라
 * (컨테이너 재시작 시 초기화되므로 서버 쪽 rename은 유지되지 않음)
 * 표시 단계에서 매핑한다.
 */
const GRAPH_DISPLAY_NAMES: Record<string, string> = {
  agent: "조서 해설 Agent",
  analyst: "대형 엑셀 분석 Agent",
  reviewer: "조서 검토 Agent",
};

function formatAssistantLabel(assistant?: Assistant | null) {
  if (!assistant) {
    return "";
  }
  const displayName =
    assistant.graph_id && GRAPH_DISPLAY_NAMES[assistant.graph_id];
  if (displayName) {
    return displayName;
  }
  if (assistant.name && assistant.graph_id) {
    return `${assistant.name}`;
  }
  return assistant.name || assistant.graph_id || assistant.assistant_id;
}

/**
 * 그래프(assistant) 선택 드롭다운.
 * 네이티브 <select>는 팝업을 브라우저(OS)가 그려 다크 모드를 못 따르므로
 * (특히 HF Space의 cross-origin iframe에서) radix Select를 쓴다.
 */
export function AssistantSelector({
  assistants,
  selectedAssistantId,
  isLoading,
  onSelect,
  onRefresh,
}: AssistantSelectorProps) {
  const t = useTranslations("chat");

  return (
    <div className="border-border bg-card flex items-center gap-1 rounded-lg border pr-1 pl-1 shadow-sm transition-all duration-200 hover:shadow-md">
      <Select
        value={selectedAssistantId ?? "none"}
        onValueChange={(value) => {
          if (value === selectedAssistantId) {
            return;
          }
          onSelect(value);
        }}
        disabled={assistants.length === 0 || isLoading}
      >
        <SelectTrigger
          id="assistant-selector"
          className="h-8 w-auto gap-1 rounded-lg border-none bg-transparent py-1 pr-1 pl-2 shadow-none"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="none">
            {isLoading
              ? t("assistant.loading")
              : assistants.length === 0
                ? t("assistant.noGraphs")
                : t("assistant.selectGraph")}
          </SelectItem>
          {assistants.map((assistant) => (
            <SelectItem
              key={assistant.assistant_id}
              value={assistant.assistant_id}
            >
              {formatAssistantLabel(assistant)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <button
        type="button"
        onClick={onRefresh}
        disabled={isLoading}
        className="hover:text-foreground inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60"
      >
        <RefreshCw
          className={cn("h-3.5 w-3.5", isLoading ? "animate-spin" : "")}
        />
      </button>
    </div>
  );
}
