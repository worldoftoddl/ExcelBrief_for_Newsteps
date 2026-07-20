#!/usr/bin/env node
/**
 * 시드 계정 생성/갱신 — credentials 모드용, 컨테이너 기동 시 실행.
 *
 * HF Space 파일시스템은 재시작·리빌드 때 초기화되므로 계정을 DB에 미리
 * 만들어둘 수 없다 — 매 기동마다 환경변수(Space 시크릿)로 upsert한다.
 * 비밀번호 교체 = 시크릿 변경 후 Space 재시작.
 *
 *   SEED_USER_EMAIL     시드 계정 이메일 (없으면 스킵)
 *   SEED_USER_PASSWORD  시드 계정 비밀번호
 *   SEED_USER_NAME      표시 이름 (기본 "검토자")
 *
 * standalone 번들의 node_modules(@prisma/client·bcryptjs)로 동작해야
 * 하므로 의존성을 추가하지 않는다. ui/ 디렉터리에서 실행할 것.
 */
import { PrismaClient } from "@prisma/client";
import { hash } from "bcryptjs";

const email = process.env.SEED_USER_EMAIL?.toLowerCase();
const password = process.env.SEED_USER_PASSWORD;

if (!email || !password) {
  console.log("[seed-users] SEED_USER_EMAIL/PASSWORD 미설정 — 시드 생략");
  process.exit(0);
}

const prisma = new PrismaClient();
try {
  const data = {
    email,
    password: await hash(password, 12),
    name: process.env.SEED_USER_NAME || "검토자",
    role: "super_admin",
    status: "active",
    approvedAt: new Date(),
  };
  await prisma.user.upsert({ where: { email }, update: data, create: data });
  console.log(`[seed-users] 시드 계정 준비 완료: ${email}`);
} finally {
  await prisma.$disconnect();
}
