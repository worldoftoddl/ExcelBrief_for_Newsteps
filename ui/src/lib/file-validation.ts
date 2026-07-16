import { toast } from "sonner";
import type { Base64ContentBlock } from "@langchain/core/messages";
import { fileToContentBlock } from "@/lib/multimodal-utils";

/**
 * Supported file types for inline (base64 content block) upload
 */
export const SUPPORTED_FILE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
  "application/pdf",
] as const;

/**
 * Document files (Excel/Word) are not inlined — they are uploaded to the
 * server's workpapers folder via /api/upload so the agent's tools can read
 * them. Extension-based check because browsers report unreliable MIME types
 * for Office documents (especially via drag & drop).
 */
export const DOCUMENT_EXTENSIONS = [".xlsx", ".xlsm", ".xls", ".docx"] as const;

export interface UploadedDocument {
  /** Original file name as selected by the user */
  filename: string;
  /** File name the server saved it under (unique within workpapers dir) */
  savedAs: string;
  size: number;
}

export function isDocumentFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return DOCUMENT_EXTENSIONS.some((ext) => name.endsWith(ext));
}

/**
 * Upload a document to the server workpapers folder. Throws with a
 * user-facing (Korean) message on failure.
 */
export async function uploadDocument(file: File): Promise<UploadedDocument> {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch("/api/upload", { method: "POST", body: form });
  } catch {
    throw new Error(
      "업로드 요청에 실패했습니다. 네트워크 상태를 확인해주세요.",
    );
  }
  const body = (await res.json().catch(() => ({}))) as {
    filename?: string;
    error?: string;
  };
  if (!res.ok || !body.filename) {
    throw new Error(
      body.error ?? `업로드에 실패했습니다 (HTTP ${res.status}).`,
    );
  }
  return { filename: file.name, savedAs: body.filename, size: file.size };
}

/**
 * Error messages for file validation
 */
const ERROR_MESSAGES = {
  INVALID_FILE_TYPE:
    "지원하지 않는 파일 형식입니다. 이미지(JPEG/PNG/GIF/WEBP), PDF, Excel(xlsx/xlsm/xls), Word(docx)만 업로드할 수 있습니다.",
  INVALID_FILE_TYPE_PASTE:
    "붙여넣은 파일 형식을 지원하지 않습니다. 이미지(JPEG/PNG/GIF/WEBP), PDF, Excel(xlsx/xlsm/xls), Word(docx)만 가능합니다.",
  DUPLICATE_FILES: (fileNames: string[]) =>
    `중복 파일: ${fileNames.join(", ")} — 같은 파일은 메시지당 한 번만 첨부할 수 있습니다.`,
} as const;

/**
 * Check if a file is already uploaded (duplicate)
 */
export function isDuplicate(
  file: File,
  existingBlocks: Base64ContentBlock[],
): boolean {
  if (file.type === "application/pdf") {
    return existingBlocks.some(
      (block) =>
        block.type === "file" &&
        block.mime_type === "application/pdf" &&
        block.metadata?.filename === file.name,
    );
  }

  if (
    SUPPORTED_FILE_TYPES.includes(
      file.type as (typeof SUPPORTED_FILE_TYPES)[number],
    )
  ) {
    return existingBlocks.some(
      (block) =>
        block.type === "image" &&
        block.metadata?.name === file.name &&
        block.mime_type === file.type,
    );
  }

  return false;
}

/**
 * Result of file validation
 */
export interface FileValidationResult {
  validFiles: File[];
  invalidFiles: File[];
  duplicateFiles: File[];
  uniqueFiles: File[];
}

/**
 * Validate a list of files against supported types and existing blocks
 */
export function validateFiles(
  files: File[],
  existingBlocks: Base64ContentBlock[],
): FileValidationResult {
  const validFiles = files.filter((file) =>
    SUPPORTED_FILE_TYPES.includes(
      file.type as (typeof SUPPORTED_FILE_TYPES)[number],
    ),
  );
  const invalidFiles = files.filter(
    (file) =>
      !SUPPORTED_FILE_TYPES.includes(
        file.type as (typeof SUPPORTED_FILE_TYPES)[number],
      ),
  );
  const duplicateFiles = validFiles.filter((file) =>
    isDuplicate(file, existingBlocks),
  );
  const uniqueFiles = validFiles.filter(
    (file) => !isDuplicate(file, existingBlocks),
  );

  return {
    validFiles,
    invalidFiles,
    duplicateFiles,
    uniqueFiles,
  };
}

/**
 * Show toast errors for invalid/duplicate files
 */
export function showFileValidationErrors(
  validation: FileValidationResult,
  isPaste = false,
): void {
  if (validation.invalidFiles.length > 0) {
    toast.error(
      isPaste
        ? ERROR_MESSAGES.INVALID_FILE_TYPE_PASTE
        : ERROR_MESSAGES.INVALID_FILE_TYPE,
    );
  }

  if (validation.duplicateFiles.length > 0) {
    toast.error(
      ERROR_MESSAGES.DUPLICATE_FILES(
        validation.duplicateFiles.map((f) => f.name),
      ),
    );
  }
}

/**
 * Process files: validate, show errors, and convert to content blocks
 */
export async function processFiles(
  files: File[],
  existingBlocks: Base64ContentBlock[],
  isPaste = false,
): Promise<Base64ContentBlock[]> {
  const validation = validateFiles(files, existingBlocks);
  showFileValidationErrors(validation, isPaste);

  if (validation.uniqueFiles.length === 0) {
    return [];
  }

  const newBlocks = await Promise.all(
    validation.uniqueFiles.map(fileToContentBlock),
  );
  return newBlocks;
}
