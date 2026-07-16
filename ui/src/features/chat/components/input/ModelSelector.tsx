import { Cpu } from "lucide-react";
import type { ModelOption } from "@/lib/models";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";

interface ModelSelectorProps {
  models: ModelOption[];
  value: string;
  onSelect: (spec: string) => void;
  disabled?: boolean;
}

/**
 * 응답 모델 선택 드롭다운 — AssistantSelector와 같은 룩앤필.
 * 목록은 /api/models가 벤더 API 키 존재 여부로 필터해 내려준다.
 * 네이티브 <select>는 팝업을 브라우저(OS)가 그려 다크 모드를 못 따르므로
 * (특히 HF Space의 cross-origin iframe에서) radix Select를 쓴다.
 */
export function ModelSelector({
  models,
  value,
  onSelect,
  disabled = false,
}: ModelSelectorProps) {
  if (models.length === 0) return null;
  return (
    <Select
      value={value}
      onValueChange={onSelect}
      disabled={disabled}
    >
      <SelectTrigger
        id="model-selector"
        aria-label="응답 모델 선택"
        className="border-border bg-card h-8 w-auto max-w-[220px] gap-1 rounded-lg py-1 pr-2 pl-2 shadow-sm transition-all duration-200 hover:shadow-md"
      >
        <Cpu className="text-muted-foreground h-3.5 w-3.5 flex-shrink-0" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {models.map((m) => (
          <SelectItem
            key={m.spec}
            value={m.spec}
          >
            {m.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
