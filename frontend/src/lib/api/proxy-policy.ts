const ALLOWED_ROOTS = new Set([
  "auth",
  "experiences",
  "jobs",
  "action-items",
  "dashboard",
]);

const ALLOWED_FORWARD_HEADERS = ["content-type", "if-match", "idempotency-key"];

export function isAllowedBackendPath(path: string[]): boolean {
  if (path.length < 3 || path[0] !== "api" || path[1] !== "v1") {
    return false;
  }

  if (path.some((segment) => segment === "" || segment === "." || segment === "..")) {
    return false;
  }

  if (!ALLOWED_ROOTS.has(path[2])) {
    return false;
  }

  return !(
    path[2] === "auth" &&
    path.length === 4 &&
    ["login", "register"].includes(path[3])
  );
}

export function forwardedRequestHeaders(
  requestHeaders: Headers,
  accessToken: string,
): Headers {
  const headers = new Headers({ authorization: `Bearer ${accessToken}` });
  for (const name of ALLOWED_FORWARD_HEADERS) {
    const value = requestHeaders.get(name);
    if (value !== null) {
      headers.set(name, value);
    }
  }
  return headers;
}

export function forwardedResponseHeaders(backendHeaders: Headers): Headers {
  const headers = new Headers();
  for (const name of ["content-type", "retry-after", "x-request-id"]) {
    const value = backendHeaders.get(name);
    if (value !== null) {
      headers.set(name, value);
    }
  }
  return headers;
}
