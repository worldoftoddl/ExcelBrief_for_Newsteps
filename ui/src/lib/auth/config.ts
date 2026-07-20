import { NextAuthConfig } from "next-auth";
import { prisma } from "./prisma";
import { getAuthProviders } from "./providers";
import {
  getAuthMode,
  usesNextAuth,
  type UserRole,
  type UserStatus,
} from "@/types/auth-mode";

/**
 * Get session strategy based on auth mode
 * - oauth: jwt (stateless)
 * - credentials: jwt (stateless)
 * - email: database (for magic link)
 */
function getSessionStrategy(): "jwt" | "database" {
  const mode = getAuthMode();
  // Email magic link works better with database sessions
  if (mode === "email") {
    return "database";
  }
  return "jwt";
}

export const authConfig: NextAuthConfig = {
  // standalone/oauth-direct 모드에서는 더미 시크릿 사용 (실제로 사용되지 않음)
  secret: usesNextAuth()
    ? process.env.NEXTAUTH_SECRET
    : "standalone-dummy-secret-not-used",
  adapter: usesNextAuth()
    ? (() => {
        // Dynamic import to avoid bundling @auth/prisma-adapter when not needed
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const { PrismaAdapter } = require("@auth/prisma-adapter");
        return PrismaAdapter(prisma);
      })()
    : undefined,
  session: {
    strategy: getSessionStrategy(),
  },
  pages: {
    signIn: "/login",
    verifyRequest: "/verify-request", // For email magic link
  },
  // HF Space는 huggingface.co 안의 cross-site iframe이라 SameSite=Lax인
  // NextAuth 기본 쿠키(세션·CSRF·콜백)가 요청에 실리지 않는다 — 선호 쿠키
  // (crossSiteCookieAttributes)와 같은 이유로 production에서 None+Secure.
  cookies:
    process.env.NODE_ENV === "production"
      ? {
          sessionToken: {
            name: "__Secure-authjs.session-token",
            options: {
              httpOnly: true,
              sameSite: "none",
              secure: true,
              path: "/",
            },
          },
          callbackUrl: {
            name: "__Secure-authjs.callback-url",
            options: { sameSite: "none", secure: true, path: "/" },
          },
          csrfToken: {
            name: "__Host-authjs.csrf-token",
            options: {
              httpOnly: true,
              sameSite: "none",
              secure: true,
              path: "/",
            },
          },
        }
      : undefined,
  trustHost: true,
  providers: usesNextAuth() ? getAuthProviders() : [],
  callbacks: {
    async signIn({ user, account }) {
      // For OAuth providers, sync user to database
      if (account?.provider && account.provider !== "credentials") {
        const email = user.email?.toLowerCase();
        if (email) {
          const existingUser = await prisma.user.findUnique({
            where: { email },
          });

          if (existingUser) {
            // Check if user is blocked
            if (
              existingUser.status === "pending" ||
              existingUser.status === "suspended"
            ) {
              return false;
            }
          } else {
            // Create new user for OAuth
            const { getNewUserStatus } = await import("./mode");
            await prisma.user.create({
              data: {
                email,
                name: user.name,
                status: getNewUserStatus(),
                role: "user",
              },
            });
          }
        }
      }
      return true;
    },
    async jwt({ token, user, trigger, account }) {
      // For OAuth, we need to fetch user from database
      if (account?.provider && account.provider !== "credentials" && user) {
        const email = user.email?.toLowerCase();
        if (email) {
          const dbUser = await prisma.user.findUnique({
            where: { email },
            select: { id: true, role: true, status: true },
          });
          if (dbUser) {
            token.id = dbUser.id;
            token.role = dbUser.role as UserRole;
            token.status = dbUser.status as UserStatus;
          }
        }
      } else if (user) {
        token.id = user.id;
        token.role = (user as { role?: UserRole }).role;
        token.status = (user as { status?: UserStatus }).status;
      }

      // Refresh user data on update trigger
      if (trigger === "update" && token.id) {
        const dbUser = await prisma.user.findUnique({
          where: { id: token.id as string },
          select: { role: true, status: true },
        });
        if (dbUser) {
          token.role = dbUser.role as UserRole;
          token.status = dbUser.status as UserStatus;
        }
      }
      return token;
    },
    async session({ session, token }) {
      if (token && session.user) {
        session.user.id = token.id as string;
        session.user.role = (token.role || "user") as UserRole;
        session.user.status = (token.status || "active") as UserStatus;
      }
      return session;
    },
    authorized({ auth, request }) {
      // For standalone and oauth-direct modes, always allow
      if (!usesNextAuth()) {
        return true;
      }
      // For other modes, check if user is authenticated
      return !!auth?.user;
    },
  },
};
