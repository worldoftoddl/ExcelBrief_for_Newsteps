import React, { useState } from "react";
import type { Base64ContentBlock } from "@langchain/core/messages";
import { MultimodalPreview } from "./MultimodalPreview";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  ChevronRight,
  FileSpreadsheet,
  FileText,
  Paperclip,
  X,
} from "lucide-react";
import type { UploadedDocument } from "@/lib/utils/file-validation";

interface ContentBlocksPreviewProps {
  blocks: Base64ContentBlock[];
  onRemove: (idx: number) => void;
  /** 조서 폴더에 업로드된 Excel/Word 문서 — 칩으로만 표시 */
  docs?: UploadedDocument[];
  onRemoveDoc?: (idx: number) => void;
  size?: "sm" | "md" | "lg";
  className?: string;
}

function DocumentChip({
  doc,
  onRemove,
}: {
  doc: UploadedDocument;
  onRemove?: () => void;
}) {
  const isExcel = !doc.savedAs.toLowerCase().endsWith(".docx");
  const Icon = isExcel ? FileSpreadsheet : FileText;
  return (
    <div className="bg-muted flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm">
      <Icon
        className={cn(
          "h-4 w-4 flex-shrink-0",
          isExcel ? "text-green-700" : "text-blue-700",
        )}
      />
      <span
        className="max-w-[220px] truncate"
        title={doc.savedAs}
      >
        {doc.savedAs}
      </span>
      {onRemove && (
        <button
          type="button"
          aria-label={`${doc.filename} 첨부 제거`}
          onClick={onRemove}
          className="text-muted-foreground hover:text-foreground ml-0.5"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

/**
 * Renders a preview of content blocks with optional remove functionality.
 * Collapsible when there are many blocks.
 */
export const ContentBlocksPreview: React.FC<ContentBlocksPreviewProps> = ({
  blocks,
  onRemove,
  docs = [],
  onRemoveDoc,
  size = "md",
  className,
}) => {
  const [isOpen, setIsOpen] = useState(true);

  const total = blocks.length + docs.length;
  if (!total) return null;

  const ChevronIcon = isOpen ? ChevronDown : ChevronRight;

  return (
    <div className={cn("p-3.5 pb-0", className)}>
      <button
        type="button"
        className="text-muted-foreground hover:text-foreground mb-1.5 flex items-center gap-1 text-xs"
        onClick={() => setIsOpen(!isOpen)}
      >
        <ChevronIcon className="h-3 w-3" />
        <Paperclip className="h-3 w-3" />
        <span>첨부 {total}개</span>
      </button>
      {isOpen && (
        <div className="flex flex-wrap gap-2">
          {docs.map((doc, idx) => (
            <DocumentChip
              key={doc.savedAs}
              doc={doc}
              onRemove={onRemoveDoc ? () => onRemoveDoc(idx) : undefined}
            />
          ))}
          {blocks.map((block, idx) => (
            <MultimodalPreview
              key={idx}
              block={block}
              removable
              onRemove={() => onRemove(idx)}
              size={size}
            />
          ))}
        </div>
      )}
    </div>
  );
};
