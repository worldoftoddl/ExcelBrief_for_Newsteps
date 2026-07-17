"use client";

import React from "react";
import { ArtifactProvider } from "@/features/chat/components/Artifact";
import { StreamProvider, type ConnectionConfig } from "@/providers/Stream";
import { ThreadContent } from "@/features/chat/components/ThreadContent";
import type { ServerAssistantData } from "@/providers/AssistantConfig";

interface ChatContentProps {
  initialAssistantData?: ServerAssistantData;
  initialConnection: ConnectionConfig;
  enableGraphSelection?: boolean;
  defaultGraphId?: string;
}

export function ChatContent({
  initialAssistantData,
  initialConnection,
  enableGraphSelection = true,
  defaultGraphId = "",
}: ChatContentProps) {
  return (
    <StreamProvider
      // connection이 바뀌면(그래프 전환 후 router.refresh) 스트림 하위 트리를
      // 리마운트한다 — MainLayoutClient의 ThreadProvider key와 같은 패턴.
      key={`${initialConnection.apiUrl}:${initialConnection.assistantId}`}
      initialAssistantData={initialAssistantData}
      connection={initialConnection}
      enableGraphSelection={enableGraphSelection}
      defaultGraphId={defaultGraphId}
    >
      <ArtifactProvider>
        <ThreadContent />
      </ArtifactProvider>
    </StreamProvider>
  );
}
