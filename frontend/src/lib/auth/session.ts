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

export function isTrustedMutationRequest(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (origin === null) {
    return false;
  }

  return origin === new URL(request.url).origin;
}
