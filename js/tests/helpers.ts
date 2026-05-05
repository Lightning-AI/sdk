/** Minimal JSON {@link Response} for mocking `globalThis.fetch`. */
export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

export function textResponse(body: string, status: number): Response {
  return new Response(body, { status });
}
