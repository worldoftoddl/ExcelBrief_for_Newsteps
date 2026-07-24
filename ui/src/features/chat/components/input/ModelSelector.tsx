import { Cpu } from "lucide-react";
import type { ModelOption } from "@/lib/models";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";

interface ModelSelectorProps {
  models: ModelOption[];
  value: string;
  onSelect: (spec: string) => void;
  disabled?: boolean;
}

/** 레지스트리 순서를 유지한 채 인접한 같은 provider끼리 묶는다. */
function groupByProvider(models: ModelOption[]) {
  const groups: { provider: string; items: ModelOption[] }[] = [];
  for (const m of models) {
    const last = groups[groups.length - 1];
    if (last?.provider === m.provider) {
      last.items.push(m);
    } else {
      groups.push({ provider: m.provider, items: [m] });
    }
  }
  return groups;
}

/**
 * 응답 모델 선택 드롭다운 — AssistantSelector와 같은 룩앤필.
 * 목록은 /api/models가 벤더 API 키 존재 여부로 필터해 내려주며,
 * 벤더(provider)별 세로 칼럼을 가로로 늘어놓는다 — 세로 단일 목록은
 * 17종 기준 뷰포트를 넘어 잘렸음(실측). 좁은 화면에서는 칼럼이 줄바꿈된다.
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
  const groups = groupByProvider(models);
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
      <SelectContent className="max-w-[min(95vw,60rem)]">
        <div className="flex flex-wrap">
          {groups.map((g) => (
            <SelectGroup
              key={g.provider}
              className="border-border min-w-[10rem] flex-1 border-r p-1 last:border-r-0"
            >
              <SelectLabel className="text-muted-foreground text-xs">
                {g.provider}
              </SelectLabel>
              {g.items.map((m) => (
                <SelectItem
                  key={m.spec}
                  value={m.spec}
                >
                  {m.label}
                </SelectItem>
              ))}
            </SelectGroup>
          ))}
        </div>
      </SelectContent>
    </Select>
  );
}
