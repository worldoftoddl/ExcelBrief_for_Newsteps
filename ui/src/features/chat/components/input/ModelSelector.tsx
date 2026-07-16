import { Cpu } from "lucide-react";
import type { ModelOption } from "@/lib/models";

interface ModelSelectorProps {
  models: ModelOption[];
  value: string;
  onSelect: (spec: string) => void;
  disabled?: boolean;
}

/**
 * 응답 모델 선택 드롭다운 — AssistantSelector와 같은 룩앤필.
 * 목록은 /api/models가 벤더 API 키 존재 여부로 필터해 내려준다.
 */
export function ModelSelector({
  models,
  value,
  onSelect,
  disabled = false,
}: ModelSelectorProps) {
  if (models.length === 0) return null;
  return (
    <div className="border-border bg-card flex h-8 items-center gap-1 rounded-lg border pr-1 pl-2 shadow-sm transition-all duration-200 hover:shadow-md">
      <Cpu className="text-muted-foreground h-3.5 w-3.5 flex-shrink-0" />
      <select
        id="model-selector"
        aria-label="응답 모델 선택"
        value={value}
        onChange={(e) => onSelect(e.target.value)}
        disabled={disabled}
        className="max-w-[180px] cursor-pointer truncate border-none bg-transparent py-1 pr-1 text-sm outline-none focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-70"
      >
        {models.map((m) => (
          <option
            key={m.spec}
            value={m.spec}
          >
            {m.label}
          </option>
        ))}
      </select>
    </div>
  );
}
