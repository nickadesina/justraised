// Conventions copied from the talent network's own API: open CORS, an
// edge cache, JSON errors as {error: {code, message}}, and an optional
// ?source= tag that is validated, echoed back and logged.

const SOURCE_RE = /^[a-zA-Z0-9._:-]+$/;

export const HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "*",
  "Cache-Control": "public, max-age=300, s-maxage=3600, stale-while-revalidate=600",
};

export function error(status: number, code: string, message: string): Response {
  return Response.json({ error: { code, message } }, { status, headers: HEADERS });
}

export type Parsed<T> = { ok: true; value: T } | { ok: false; response: Response };

export function readSource(url: URL, route: string): Parsed<string | undefined> {
  const source = url.searchParams.get("source") ?? undefined;
  if (source !== undefined && (source.length > 64 || !SOURCE_RE.test(source))) {
    return { ok: false, response: error(400, "bad_source", "source must match ^[a-zA-Z0-9._:-]+$ and be at most 64 characters") };
  }
  // One structured line per call; Vercel's log drain is the attribution record.
  console.log(JSON.stringify({ event: "api", route, source: source ?? null, query: url.search }));
  return { ok: true, value: source };
}

export function readPage(url: URL): Parsed<number> {
  const raw = url.searchParams.get("page");
  if (raw === null || raw === "") return { ok: true, value: 0 };
  const page = Number(raw);
  if (!Number.isInteger(page) || page < 0 || page > 200) {
    return { ok: false, response: error(400, "bad_page", "page must be an integer from 0 to 200") };
  }
  return { ok: true, value: page };
}

export function options(): Response {
  return new Response(null, { status: 204, headers: HEADERS });
}
