export const SESSION_COOKIE_NAME = "careerops_access_token";
export const SESSION_MAX_AGE_SECONDS = 30 * 60;

type SessionCookieOptions = {
  httpOnly: true;
  sameSite: "lax";
  secure: boolean;
  path: "/";
  maxAge: number;
};

export function sessionCookieOptions(isProduction: boolean): SessionCookieOptions {
  return {
    httpOnly: true,
    sameSite: "lax",
    secure: isProduction,
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  };
}

export function isTrustedMutationRequest(
  request: Request,
  configuredOrigin = process.env.CAREEROPS_FRONTEND_ORIGIN,
): boolean {
  const origin = request.headers.get("origin");
  if (origin === null) {
    return false;
  }

  if (configuredOrigin === undefined) {
    return origin === new URL(request.url).origin;
  }

  try {
    const trustedUrl = new URL(configuredOrigin);
    if (
      !["http:", "https:"].includes(trustedUrl.protocol) ||
      trustedUrl.username ||
      trustedUrl.password ||
      trustedUrl.pathname !== "/" ||
      trustedUrl.search ||
      trustedUrl.hash
    ) {
      return false;
    }
    return origin === trustedUrl.origin;
  } catch {
    return false;
  }
}
