import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { BookOpen, LoaderCircle } from "lucide-react";
import type { ChatConfig } from "@/lib/config/client";
import { CHAT_STARTERS } from "@/configs/site";
import { GRAPH_META } from "@/configs/graphs";
import { useAssistantConfig } from "@/shared/hooks/useAssistantConfig";
import { MarkdownText } from "./content/MarkdownText";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/components/ui/dialog";

interface WelcomeScreenProps {
  config: ChatConfig;
  chatWidth: "default" | "wide";
  isSchemaLoading: boolean;
  /** 예시 질문 클릭 시 입력창을 채운다 */
  onStarterClick?: (text: string) => void;
}

/** /full-description.md를 다이얼로그로 보여주는 사용 안내 버튼 */
function GuideDialog() {
  const [open, setOpen] = useState(false);
  const [markdown, setMarkdown] = useState<string | null>(null);

  useEffect(() => {
    if (!open || markdown !== null) return;
    fetch("/full-description.md")
      .then((res) => (res.ok ? res.text() : Promise.reject(res.status)))
      .then(setMarkdown)
      .catch(() => setMarkdown("안내 문서를 불러오지 못했습니다."));
  }, [open, markdown]);

  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
    >
      <DialogTrigger asChild>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground flex items-center gap-1.5 text-sm underline-offset-4 hover:underline"
        >
          <BookOpen className="h-4 w-4" />
          사용 안내 · 준비된 조서 보기
        </button>
      </DialogTrigger>
      <DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>사용 안내</DialogTitle>
        </DialogHeader>
        {markdown === null ? (
          <LoaderCircle className="text-muted-foreground mx-auto h-6 w-6 animate-spin" />
        ) : (
          <MarkdownText>{markdown}</MarkdownText>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function WelcomeScreen({
  config,
  chatWidth,
  isSchemaLoading,
  onStarterClick,
}: WelcomeScreenProps) {
  // 선택된 그래프에 맞는 소개문·예시 질문 (미등록 graph_id는 기본값)
  const { assistantId, assistants } = useAssistantConfig();
  const graphId = assistants.find(
    (a) => a.assistant_id === assistantId,
  )?.graph_id;
  const graphMeta = graphId ? GRAPH_META[graphId] : undefined;
  const description = graphMeta?.description ?? config.branding.description;
  const starters = graphMeta?.starters ?? CHAT_STARTERS;

  return (
    <div
      className={cn(
        "mx-auto flex w-full flex-col items-center gap-6",
        chatWidth === "default" ? "max-w-3xl" : "max-w-5xl",
      )}
    >
      <div className="flex flex-col items-center gap-3">
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={config.branding.logoPath}
            alt="Logo"
            width={config.branding.logoWidth * 1.5}
            height={config.branding.logoHeight * 1.5}
            className="flex-shrink-0"
          />
          <h1 className="text-2xl font-semibold tracking-tight">
            {config.branding.appName}
          </h1>
        </div>
        {description && (
          <p className="text-muted-foreground text-center text-base">
            {description}
          </p>
        )}
        <GuideDialog />
      </div>

      {onStarterClick && (
        <div className="flex flex-wrap justify-center gap-2 px-4">
          {starters.map((starter) => (
            <button
              key={starter}
              type="button"
              onClick={() => onStarterClick(starter)}
              className="border-border bg-card text-foreground/80 hover:bg-accent hover:text-foreground max-w-full truncate rounded-full border px-3.5 py-1.5 text-sm shadow-sm transition-colors"
              title={starter}
            >
              {starter}
            </button>
          ))}
        </div>
      )}

      {isSchemaLoading && (
        <LoaderCircle className="text-muted-foreground h-6 w-6 animate-spin" />
      )}
    </div>
  );
}
