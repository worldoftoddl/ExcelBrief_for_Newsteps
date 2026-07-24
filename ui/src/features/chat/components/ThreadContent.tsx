/**
 * ThreadContent - Chat content without sidebar
 * The sidebar is now rendered in the shared layout (MainLayoutClient)
 */

import { useEffect, useRef, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { TIMING } from "@/lib/constants";
import { useStreamContext } from "@/features/chat/hooks/useStreamContext";
import { useState } from "react";
import { useQueryState, parseAsBoolean } from "nuqs";
import { StickToBottom } from "use-stick-to-bottom";
import { toast } from "sonner";
import { useMediaQuery } from "@/shared/hooks/useMediaQuery";
import { useFileUpload } from "@/shared/hooks/useFileUpload";
import {
  fetchAvailableModels,
  getStoredModelSpec,
  storeModelSpec,
  DEFAULT_MODEL_SPEC,
  type ModelOption,
} from "@/lib/models";
import { useSettings } from "@/shared/hooks/useSettings";
import { useAssistantConfig } from "@/shared/hooks/useAssistantConfig";
import { useSchemaUI } from "@/features/chat/hooks/useSchemaUI";
import { UnifiedInputArea } from "./schema-ui";
import { updateAssistantIdAction } from "@/app/actions";
import { MessageList } from "./MessageList";
import { TracingSidebar } from "./sidebar/TracingSidebar";
import { ThreadErrorBoundary } from "./ThreadErrorBoundary";
import { useLangSmithRuns } from "@/features/chat/hooks/useLangSmithRuns";
import { useStreamingView } from "@/features/chat/hooks/useStreamingView";
import { useMessageSubmit } from "@/features/chat/hooks/useMessageSubmit";
import { StickyToBottomContent, ScrollToBottom } from "./ScrollComponents";
import { WelcomeScreen } from "./WelcomeScreen";
import {
  mapRunToToolCallEvent,
  mapRunToToolResultEvent,
  mapRunToLLMEvent,
  mapRunToMiddlewareEvent,
} from "@/types/langsmith";
import { type LangSmithTimelineEvents } from "@/types/timeline";

export function ThreadContent() {
  const t = useTranslations("chat");
  const { config, userSettings, updateUserSettings, globalSettings } =
    useSettings();
  const [threadId, setThreadId] = useQueryState("threadId");
  const router = useRouter();

  // Tracing panel state
  const sidebarOpen = userSettings.tracingPanelOpen;
  const setSidebarOpen = useCallback(
    (value: boolean | ((prev: boolean) => boolean)) => {
      const newValue = typeof value === "function" ? value(sidebarOpen) : value;
      updateUserSettings({ tracingPanelOpen: newValue });
    },
    [sidebarOpen, updateUserSettings],
  );

  const [compactView, setCompactView] = useQueryState(
    "compactView",
    parseAsBoolean.withDefault(true),
  );
  const [input, setInput] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const {
    contentBlocks,
    setContentBlocks,
    handleFileUpload,
    dropRef,
    removeBlock,
    dragOver,
    handlePaste,
    uploadedDocs,
    removeDoc,
    resetDocs,
    docsUploading,
  } = useFileUpload();
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");

  // 응답 모델 선택 — 서버가 벤더 API 키 존재 여부로 필터한 목록만 노출.
  // 선택값은 localStorage에 저장되고 useMessageSubmit이 submit 시점에 읽는다.
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([]);
  const [modelSpec, setModelSpec] = useState(getStoredModelSpec);
  useEffect(() => {
    fetchAvailableModels().then((models) => {
      setAvailableModels(models);
      // 저장된 선택이 목록에서 사라졌으면(레지스트리 교체·키 회수 등)
      // 기본 모델로 되돌린다 — 기본도 없으면 첫 모델
      if (
        models.length > 0 &&
        !models.some((m) => m.spec === getStoredModelSpec())
      ) {
        const fallback =
          models.find((m) => m.spec === DEFAULT_MODEL_SPEC) ?? models[0];
        setModelSpec(fallback.spec);
        storeModelSpec(fallback.spec);
      }
    });
  }, []);
  const handleModelChange = useCallback((spec: string) => {
    setModelSpec(spec);
    storeModelSpec(spec);
  }, []);

  // Schema UI for dynamic form fields
  const schemaUI = useSchemaUI();
  const { parsedSchema, getSubmitPayload, getDisplayPayload, resetForm } =
    schemaUI;
  const isFormMode = parsedSchema.uiMode === "form";

  const stream = useStreamContext();
  const messages = stream.messages;
  const isLoading = stream.isLoading;
  const nodeUpdates = stream.nodeUpdates;
  const progressEvents = stream.progressEvents;
  const updateNodeCompletedOutput = stream.updateNodeCompletedOutput;
  const messageNodeMap = stream.messageNodeMap;
  const {
    assistantId: currentAssistantId,
    assistants,
    assistantsLoading,
    refetchAssistants,
    finalNodeNames,
  } = useAssistantConfig();

  const isAssistantSelected = Boolean(currentAssistantId?.trim());

  // Message submit logic (extracted hook)
  const {
    handleSubmit,
    handleRegenerate,
    handleRetry,
    handleFormSubmit,
    firstTokenReceived,
    setFirstTokenReceived,
    formSubmissions,
  } = useMessageSubmit({
    stream,
    isAssistantSelected,
    input,
    setInput,
    contentBlocks,
    setContentBlocks,
    uploadedDocs,
    resetDocs,
    getSubmitPayload,
    getDisplayPayload,
    resetForm,
    parsedSchema,
  });

  // LangSmith API (disabled when env vars not configured)
  const langsmithEnabled = config.langsmithEnabled;
  const {
    runs: allRuns,
    middlewareRuns: langSmithMiddlewareRuns,
    toolRuns: langSmithToolRuns,
    llmRuns: langSmithLLMRuns,
    loading: langSmithLoading,
    refetch: refetchLangSmith,
  } = useLangSmithRuns(langsmithEnabled ? threadId : null, null, {
    pollingInterval: TIMING.POLLING_INTERVAL,
    autoPolling: langsmithEnabled && isLoading,
  });

  // LangSmith runs to timeline events
  const langSmithEvents: LangSmithTimelineEvents = useMemo(() => {
    return {
      middlewares: langSmithMiddlewareRuns.map(mapRunToMiddlewareEvent),
      toolCalls: langSmithToolRuns.map(mapRunToToolCallEvent),
      toolResults: langSmithToolRuns
        .filter((run) => run.status === "success" || run.status === "error")
        .map(mapRunToToolResultEvent),
      llmEnds: langSmithLLMRuns.map(mapRunToLLMEvent),
    };
  }, [langSmithMiddlewareRuns, langSmithToolRuns, langSmithLLMRuns]);

  // Streaming view state (flat list with grouping)
  const {
    progress,
    todoLifecycle,
    hasVisibleContent,
    showTaskView,
    activeLeafTasks,
    activityItems,
  } = useStreamingView(allRuns, isLoading, messages, {
    nodeUpdates,
    progressEvents,
    finalNodeNames,
    updateNodeCompletedOutput,
    getMessagesMetadata: stream.getMessagesMetadata,
    messageNodeMap,
    stateTodos: stream.values?.todos,
  });

  // Refetch LangSmith when streaming completes
  const prevIsLoading = useRef(isLoading);
  useEffect(() => {
    if (prevIsLoading.current && !isLoading) {
      setTimeout(() => {
        refetchLangSmith();
      }, TIMING.LANGSMITH_REFETCH_DELAY);
    }
    prevIsLoading.current = isLoading;
  }, [isLoading, refetchLangSmith]);

  // Reset on threadId change (any thread switch, not just null)
  const prevThreadId = useRef(threadId);
  useEffect(() => {
    if (prevThreadId.current !== threadId) {
      // Always clear streaming state on thread switch to prevent stale indicators
      stream.clearNodeUpdates();
      setFirstTokenReceived(false);

      if (threadId === null) {
        setSidebarOpen(false);
        setInput("");
        setContentBlocks([]);
      }
    }
    prevThreadId.current = threadId;
  }, [
    threadId,
    setSidebarOpen,
    setContentBlocks,
    stream,
    setFirstTokenReceived,
  ]);

  const lastError = useRef<string | undefined>(undefined);

  const assistantSelectValue = useMemo(
    () => currentAssistantId?.trim() || "none",
    [currentAssistantId],
  );

  // 그래프 전환: 쿠키 갱신 후 router.refresh()로 서버 컴포넌트만 다시 실행한다.
  // upstream은 window.location.reload()를 썼지만 전체 리로드는 화면이 하얗게
  // 깜빡인다 — layout/page가 새 쿠키를 읽어 내려보내면 connection key 리마운트
  // (MainLayoutClient·ChatContent)가 하위 트리를 새 그래프로 교체한다.
  // 스레드는 그래프 종속이므로 전환 시 새 채팅으로 시작한다.
  const handleAssistantChange = useCallback(
    async (value: string) => {
      if (value === "none") {
        if (currentAssistantId) {
          await updateAssistantIdAction(null);
          await setThreadId(null);
          router.refresh();
        }
        return;
      }

      const trimmedValue = value.trim();
      if (!trimmedValue || trimmedValue === currentAssistantId?.trim()) {
        return;
      }

      await updateAssistantIdAction(trimmedValue);
      await setThreadId(null);
      toast.success(t("graphChanged"), {
        description: t("graphChangedDescription", { assistantId: value }),
      });
      router.refresh();
    },
    [currentAssistantId, t, router, setThreadId],
  );

  useEffect(() => {
    if (!stream.error) {
      lastError.current = undefined;
      return;
    }
    try {
      const message = (stream.error as { message?: string }).message;
      if (!message || lastError.current === message) {
        return;
      }

      lastError.current = message;
      toast.error("An error occurred. Please try again.", {
        description: (
          <p>
            <strong>Error:</strong> <code>{message}</code>
          </p>
        ),
        richColors: true,
        closeButton: true,
      });
    } catch {
      // no-op
    }
  }, [stream.error]);

  const chatStarted =
    !!threadId || !!messages.length || formSubmissions.length > 0;

  return (
    <ThreadErrorBoundary>
      <div className="relative flex h-full w-full overflow-hidden">
        <div
          className={cn(
            "relative flex min-w-0 flex-1 flex-col overflow-hidden",
            !chatStarted && "grid-rows-[1fr]",
          )}
        >
          <StickToBottom
            resize="smooth"
            className="relative flex-1 overflow-hidden"
          >
            <StickyToBottomContent
              className={cn(
                "[&::-webkit-scrollbar-thumb]:bg-border absolute inset-0 overflow-y-scroll [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent",
                !chatStarted &&
                  "mt-0 flex flex-col items-stretch justify-center",
                chatStarted && "grid grid-rows-[1fr_auto]",
                userSettings.chatWidth === "default" ? "px-4" : "px-2",
              )}
              contentClassName={cn(
                messages.length > 0 || formSubmissions.length > 0
                  ? "pt-8 pb-16 flex flex-col gap-4"
                  : "",
                "mx-auto w-full",
                userSettings.chatWidth === "default"
                  ? "max-w-3xl"
                  : "max-w-5xl",
              )}
              content={
                <MessageList
                  messages={messages}
                  isLoading={isLoading}
                  isFormMode={isFormMode}
                  formSubmissions={formSubmissions}
                  compactView={compactView ?? true}
                  hasVisibleContent={hasVisibleContent}
                  showTaskView={showTaskView}
                  progress={progress}
                  activeLeafTasks={activeLeafTasks}
                  activityItems={activityItems}
                  finalNodeNames={finalNodeNames}
                  todoLifecycle={todoLifecycle}
                  selectedTaskId={selectedTaskId}
                  onSelectTask={setSelectedTaskId}
                  handleRegenerate={handleRegenerate}
                  firstTokenReceived={firstTokenReceived}
                  interrupt={stream.interrupt}
                  threadId={threadId}
                  streamError={stream.error}
                  onRetry={handleRetry}
                />
              }
              footer={
                <div className="sticky bottom-0 flex flex-col items-center gap-10 bg-none">
                  {!chatStarted && (
                    <WelcomeScreen
                      config={config}
                      chatWidth={userSettings.chatWidth}
                      isSchemaLoading={schemaUI.isLoading}
                      onStarterClick={setInput}
                    />
                  )}

                  <ScrollToBottom className="animate-in fade-in-0 zoom-in-95 absolute bottom-full left-1/2 mb-4 -translate-x-1/2" />

                  <div
                    className={cn(
                      "relative z-10 mx-auto mb-8 w-full",
                      userSettings.chatWidth === "default"
                        ? "max-w-3xl"
                        : "max-w-5xl",
                    )}
                  >
                    <UnifiedInputArea
                      schemaUI={schemaUI}
                      isFormMode={isFormMode}
                      onFormSubmit={handleFormSubmit}
                      input={input}
                      onInputChange={setInput}
                      onChatSubmit={handleSubmit}
                      contentBlocks={contentBlocks}
                      onRemoveBlock={removeBlock}
                      uploadedDocs={uploadedDocs}
                      onRemoveDoc={removeDoc}
                      docsUploading={docsUploading}
                      onFileUpload={handleFileUpload}
                      onPaste={handlePaste}
                      dropRef={dropRef}
                      dragOver={dragOver}
                      isLoading={isLoading}
                      onStop={() => {
                        stream.stop();
                        stream.deactivateAllNodes();
                      }}
                      isAssistantSelected={isAssistantSelected}
                      enableFileUpload={config.buttons.enableFileUpload}
                      fileUploadMode={config.buttons.fileUploadMode}
                      placeholder={config.buttons.chatInputPlaceholder}
                      compactView={compactView ?? true}
                      onCompactViewChange={(value) => setCompactView(value)}
                      assistants={assistants}
                      selectedAssistantId={assistantSelectValue}
                      assistantsLoading={assistantsLoading}
                      onAssistantChange={handleAssistantChange}
                      onRefreshAssistants={refetchAssistants}
                      isChatPage={!!threadId}
                      models={availableModels}
                      modelSpec={modelSpec}
                      onModelChange={handleModelChange}
                      enableGraphSelection={
                        globalSettings["features.enableGraphSelection"]
                      }
                      enableAdvancedInput={
                        globalSettings["features.enableAdvancedInput"]
                      }
                    />
                  </div>
                </div>
              }
            />
          </StickToBottom>
        </div>

        {/* LangSmith Tracing Sidebar */}
        <TracingSidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          langSmithEvents={langSmithEvents}
          langSmithLoading={langSmithLoading}
          onRefresh={refetchLangSmith}
          selectedTaskId={selectedTaskId}
          onSelectTask={setSelectedTaskId}
          isLargeScreen={isLargeScreen}
        />
      </div>
    </ThreadErrorBoundary>
  );
}
