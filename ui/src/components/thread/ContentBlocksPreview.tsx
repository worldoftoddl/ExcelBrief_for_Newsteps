import React from "react";
import type { Base64ContentBlock } from "@langchain/core/messages";
import { FileSpreadsheet, FileText, X as XIcon } from "lucide-react";
import { MultimodalPreview } from "./MultimodalPreview";
import { cn } from "@/lib/utils";
import type { UploadedDocument } from "@/lib/file-validation";

interface ContentBlocksPreviewProps {
  blocks: Base64ContentBlock[];
  onRemove: (idx: number) => void;
  docs?: UploadedDocument[];
  onRemoveDoc?: (idx: number) => void;
  size?: "sm" | "md" | "lg";
  className?: string;
}

/**
 * Renders a preview of content blocks (inline images/PDFs) plus uploaded
 * document chips (Excel/Word saved to the server workpapers folder).
 */
export const ContentBlocksPreview: React.FC<ContentBlocksPreviewProps> = ({
  blocks,
  onRemove,
  docs = [],
  onRemoveDoc,
  size = "md",
  className,
}) => {
  if (!blocks.length && !docs.length) return null;
  return (
    <div className={cn("flex flex-wrap gap-2 p-3.5 pb-0", className)}>
      {blocks.map((block, idx) => (
        <MultimodalPreview
          key={idx}
          block={block}
          removable
          onRemove={() => onRemove(idx)}
          size={size}
        />
      ))}
      {docs.map((doc, idx) => {
        const isWord = doc.savedAs.toLowerCase().endsWith(".docx");
        const Icon = isWord ? FileText : FileSpreadsheet;
        return (
          <div
            key={doc.savedAs}
            className="relative flex items-start gap-2 rounded-md border bg-gray-100 px-3 py-2"
          >
            <Icon
              className={cn(
                "flex-shrink-0",
                isWord ? "text-blue-700" : "text-green-700",
                size === "sm" ? "h-5 w-5" : "h-7 w-7",
              )}
            />
            <span
              className="min-w-0 flex-1 text-sm break-all text-gray-800"
              style={{ wordBreak: "break-all", whiteSpace: "pre-wrap" }}
            >
              {doc.savedAs}
            </span>
            {onRemoveDoc && (
              <button
                type="button"
                className="ml-2 self-start rounded-full bg-gray-200 p-1 text-gray-600 hover:bg-gray-300"
                onClick={() => onRemoveDoc(idx)}
                aria-label="첨부 문서 제거"
              >
                <XIcon className="h-4 w-4" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
};
