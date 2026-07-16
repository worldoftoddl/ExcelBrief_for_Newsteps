import { mkdir, writeFile } from "fs/promises";
import { existsSync } from "fs";
import path from "path";

// langgraph 서버와 같은 파일시스템을 공유하므로(단일 컨테이너/로컬 동일 리포)
// WORKPAPERS_DIR에 저장하면 에이전트의 list_workpapers·excel_*·read_document가
// 즉시 읽을 수 있다. 이 정적 라우트는 catch-all([..._path]) 프록시보다 우선 매칭된다.
export const runtime = "nodejs";

const ALLOWED_EXTENSIONS = new Set([".xlsx", ".xlsm", ".xls", ".docx"]);
const MAX_BYTES = 20 * 1024 * 1024; // 20MB

function workpapersDir(): string {
  // 컨테이너에서는 ENV로 주입, 로컬 dev(cwd=ui/)에서는 리포의 data/workpapers
  return (
    process.env.WORKPAPERS_DIR ??
    path.resolve(process.cwd(), "..", "data", "workpapers")
  );
}

function sanitizeBaseName(name: string): string {
  // 경로 구분자·제어문자만 치환하고 한글 등 유니코드 파일명은 보존한다
  return path
    .basename(name)
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_")
    .trim();
}

function uniqueName(dir: string, base: string): string {
  const ext = path.extname(base);
  const stem = base.slice(0, base.length - ext.length);
  let candidate = base;
  // 기존 파일(데모 조서 포함)을 방문자 업로드가 덮어쓰지 않도록 접미사를 붙인다
  for (let i = 1; existsSync(path.join(dir, candidate)); i += 1) {
    candidate = `${stem} (${i})${ext}`;
  }
  return candidate;
}

export async function POST(req: Request): Promise<Response> {
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return Response.json(
      { error: "multipart/form-data 요청이 아닙니다." },
      { status: 400 },
    );
  }

  const file = form.get("file");
  if (!(file instanceof File)) {
    return Response.json(
      { error: "file 필드에 파일이 없습니다." },
      { status: 400 },
    );
  }

  const ext = path.extname(file.name).toLowerCase();
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return Response.json(
      { error: `지원하지 않는 형식입니다 (${ext || "확장자 없음"}). xlsx, xlsm, xls, docx만 업로드할 수 있습니다.` },
      { status: 400 },
    );
  }
  if (file.size > MAX_BYTES) {
    return Response.json(
      { error: `파일이 너무 큽니다 (${(file.size / 1024 / 1024).toFixed(1)}MB). 최대 20MB까지 업로드할 수 있습니다.` },
      { status: 413 },
    );
  }

  const dir = workpapersDir();
  try {
    await mkdir(dir, { recursive: true });
    const base = sanitizeBaseName(file.name) || `업로드${ext}`;
    const savedAs = uniqueName(dir, base);
    await writeFile(
      path.join(dir, savedAs),
      Buffer.from(await file.arrayBuffer()),
    );
    return Response.json({ filename: savedAs });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "unknown";
    return Response.json(
      { error: `파일 저장에 실패했습니다: ${message}` },
      { status: 500 },
    );
  }
}
