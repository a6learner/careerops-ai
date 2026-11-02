// Mirrors the durable error codes in src/careerops/domain/{parse_runs,analysis_runs,assisted_imports}.py.
const RUN_ERROR_MESSAGES: Record<string, string> = {
  PARSER_FAILED: "The requirement parser could not complete. Try parsing again.",
  PARSER_OUTPUT_INVALID: "The parser returned output that failed schema validation, so nothing was saved.",
  ANALYSIS_INPUT_CHANGED: "Your experiences or the job changed while analysis was running. Start a new analysis.",
  MATCHER_FAILED: "Evidence matching could not complete. Try again.",
  MATCHER_OUTPUT_INVALID: "The matcher returned output that failed validation, so no evidence claims were saved.",
  MATCHER_OUTPUT_INVALID_JSON: "The matcher returned malformed output, so no evidence claims were saved.",
  MATCHER_OUTPUT_INVALID_SCHEMA: "The matcher output did not match the expected schema, so no evidence claims were saved.",
  MATCHER_OUTPUT_INVALID_CONTRACT: "The matcher did not return one valid answer for every requirement, so no evidence claims were saved.",
  MATCHER_PROVIDER_DISABLED: "The evidence matcher is disabled in this environment.",
  MATCHER_PROVIDER_MISCONFIGURED: "The evidence matcher is not configured correctly. Check the worker settings.",
  MATCHER_PROVIDER_TIMEOUT: "The matching provider timed out. Try again in a moment.",
  MATCHER_PROVIDER_RATE_LIMITED: "The matching provider is rate limited. Wait a little before retrying.",
  MATCHER_PROVIDER_UNAVAILABLE: "The matching provider is unavailable. Try again later.",
  MATCHER_PROVIDER_FAILED: "The matching provider returned an error. Try again.",
  ENCRYPTED_DOCUMENT: "The document is password protected. Upload an unprotected copy.",
  EMPTY_TEXT: "No readable text was found. Scanned PDFs are not supported yet.",
  EXTRACTOR_FAILED: "The document text could not be extracted.",
  INVALID_ARCHIVE: "The document file appears to be damaged.",
  UNSUPPORTED_DOCUMENT: "This document format is not supported.",
  SEARCH_FAILED: "Job search could not complete. Try again.",
  SEARCH_OUTPUT_INVALID: "The search provider returned invalid results, so nothing was saved.",
};

export function describeRunError(code: string | null): string {
  if (!code) return "The run failed without a recorded reason.";
  return RUN_ERROR_MESSAGES[code] ?? "The run failed. Try again.";
}
