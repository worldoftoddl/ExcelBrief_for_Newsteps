import { useState, useRef, useEffect, ChangeEvent } from "react";
import type { Base64ContentBlock } from "@langchain/core/messages";
import { toast } from "sonner";
import {
  isDocumentFile,
  processFiles,
  uploadDocument,
  type UploadedDocument,
} from "@/lib/file-validation";

interface UseFileUploadOptions {
  initialBlocks?: Base64ContentBlock[];
}

export function useFileUpload({
  initialBlocks = [],
}: UseFileUploadOptions = {}) {
  const [contentBlocks, setContentBlocks] =
    useState<Base64ContentBlock[]>(initialBlocks);
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocument[]>([]);
  const [pendingDocCount, setPendingDocCount] = useState(0);
  const dropRef = useRef<HTMLDivElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const dragCounter = useRef(0);

  /**
   * Excel/Word 문서는 서버 조서 폴더에 업로드하고 칩으로만 표시한다.
   * 나머지(이미지·PDF)는 기존대로 base64 콘텐츠 블록으로 인라인한다.
   */
  const ingestFiles = async (files: File[], isPaste: boolean) => {
    const docs = files.filter(isDocumentFile);
    const rest = files.filter((f) => !isDocumentFile(f));

    for (const doc of docs) {
      if (uploadedDocs.some((d) => d.filename === doc.name)) {
        toast.error(`중복 파일: ${doc.name} — 이미 첨부되어 있습니다.`);
        continue;
      }
      setPendingDocCount((n) => n + 1);
      try {
        const uploaded = await uploadDocument(doc);
        setUploadedDocs((prev) =>
          prev.some((d) => d.filename === uploaded.filename)
            ? prev
            : [...prev, uploaded],
        );
      } catch (error: unknown) {
        toast.error(
          error instanceof Error ? error.message : "업로드에 실패했습니다.",
        );
      } finally {
        setPendingDocCount((n) => n - 1);
      }
    }

    if (rest.length > 0) {
      const newBlocks = await processFiles(rest, contentBlocks, isPaste);
      if (newBlocks.length > 0) {
        setContentBlocks((prev) => [...prev, ...newBlocks]);
      }
    }
  };

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    await ingestFiles(Array.from(files), false);

    e.target.value = "";
  };

  // Drag and drop handlers
  useEffect(() => {
    if (!dropRef.current) return;

    // Global drag events with counter for robust dragOver state
    const handleWindowDragEnter = (e: DragEvent) => {
      if (e.dataTransfer?.types?.includes("Files")) {
        dragCounter.current += 1;
        setDragOver(true);
      }
    };
    const handleWindowDragLeave = (e: DragEvent) => {
      if (e.dataTransfer?.types?.includes("Files")) {
        dragCounter.current -= 1;
        if (dragCounter.current <= 0) {
          setDragOver(false);
          dragCounter.current = 0;
        }
      }
    };
    const handleWindowDrop = async (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter.current = 0;
      setDragOver(false);

      if (!e.dataTransfer) return;

      await ingestFiles(Array.from(e.dataTransfer.files), false);
    };
    const handleWindowDragEnd = (e: DragEvent) => {
      dragCounter.current = 0;
      setDragOver(false);
    };
    window.addEventListener("dragenter", handleWindowDragEnter);
    window.addEventListener("dragleave", handleWindowDragLeave);
    window.addEventListener("drop", handleWindowDrop);
    window.addEventListener("dragend", handleWindowDragEnd);

    // Prevent default browser behavior for dragover globally
    const handleWindowDragOver = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener("dragover", handleWindowDragOver);

    // Remove element-specific drop event (handled globally)
    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(true);
    };
    const handleDragEnter = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(true);
    };
    const handleDragLeave = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);
    };
    const element = dropRef.current;
    element.addEventListener("dragover", handleDragOver);
    element.addEventListener("dragenter", handleDragEnter);
    element.addEventListener("dragleave", handleDragLeave);

    return () => {
      element.removeEventListener("dragover", handleDragOver);
      element.removeEventListener("dragenter", handleDragEnter);
      element.removeEventListener("dragleave", handleDragLeave);
      window.removeEventListener("dragenter", handleWindowDragEnter);
      window.removeEventListener("dragleave", handleWindowDragLeave);
      window.removeEventListener("drop", handleWindowDrop);
      window.removeEventListener("dragend", handleWindowDragEnd);
      window.removeEventListener("dragover", handleWindowDragOver);
      dragCounter.current = 0;
    };
  }, [contentBlocks, uploadedDocs]);

  const removeBlock = (idx: number) => {
    setContentBlocks((prev) => prev.filter((_, i) => i !== idx));
  };

  const resetBlocks = () => setContentBlocks([]);

  /**
   * Handle paste event for files (images, PDFs)
   * Can be used as onPaste={handlePaste} on a textarea or input
   */
  const handlePaste = async (
    e: React.ClipboardEvent<HTMLTextAreaElement | HTMLInputElement>,
  ) => {
    const items = e.clipboardData.items;
    if (!items) return;

    const files: File[] = [];
    for (let i = 0; i < items.length; i += 1) {
      const item = items[i];
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) files.push(file);
      }
    }

    if (files.length === 0) {
      return;
    }

    e.preventDefault();

    await ingestFiles(files, true);
  };

  const removeDoc = (idx: number) => {
    setUploadedDocs((prev) => prev.filter((_, i) => i !== idx));
  };

  const resetDocs = () => setUploadedDocs([]);

  return {
    contentBlocks,
    setContentBlocks,
    handleFileUpload,
    dropRef,
    removeBlock,
    resetBlocks,
    dragOver,
    handlePaste,
    uploadedDocs,
    removeDoc,
    resetDocs,
    docsUploading: pendingDocCount > 0,
  };
}
