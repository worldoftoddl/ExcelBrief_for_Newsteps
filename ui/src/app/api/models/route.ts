import { existsSync, readFileSync } from "fs";
import path from "path";
import { MODEL_REGISTRY } from "@/lib/models";

// 컨테이너에서는 langgraph 서버와 같은 환경변수를 공유하므로 process.env로
// 벤더 API 키 존재 여부를 판정한다. 로컬 dev에서는 키가 리포 루트 .env에만
// 있으므로(Next는 ui/.env만 로드) 파일에서 존재 여부만 확인한다 — 값은
// 클라이언트로 나가지 않는다. 이 정적 라우트는 catch-all([..._path])보다
// 우선 매칭된다.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

let rootEnvKeys: Set<string> | null = null;

function keysFromRootEnv(): Set<string> {
  if (rootEnvKeys) return rootEnvKeys;
  rootEnvKeys = new Set();
  const rootEnv = path.resolve(process.cwd(), "..", ".env");
  if (existsSync(rootEnv)) {
    for (const line of readFileSync(rootEnv, "utf-8").split("\n")) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$/);
      if (m && m[2].length > 0) rootEnvKeys.add(m[1]);
    }
  }
  return rootEnvKeys;
}

function envHasKey(key: string): boolean {
  if ((process.env[key] ?? "").length > 0) return true;
  return keysFromRootEnv().has(key);
}

export async function GET(): Promise<Response> {
  const models = MODEL_REGISTRY.filter((m) => m.envKeys.some(envHasKey)).map(
    ({ spec, label, provider }) => ({ spec, label, provider }),
  );
  return Response.json({ models });
}
