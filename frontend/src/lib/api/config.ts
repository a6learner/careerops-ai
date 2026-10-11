import "server-only";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export function getApiBaseUrl(): URL {
  const configured = process.env.CAREEROPS_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  const url = new URL(configured);

  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
    throw new Error("CAREEROPS_API_BASE_URL must be an HTTP(S) URL without credentials.");
  }

  return url;
}

export function buildBackendUrl(pathname: string, search = ""): URL {
  const baseUrl = getApiBaseUrl();
  const url = new URL(pathname, baseUrl);
  url.search = search;
  return url;
}
