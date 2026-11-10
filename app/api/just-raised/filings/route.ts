// GET /api/just-raised/filings[?slug=...]
// The Form D detail behind each collection member, keyed by talent-network
// slug. This is additive: none of it fits their member schema, so it lives
// beside the collection endpoint instead of inside it.
import { HEADERS, error, options, readSource } from "@/lib/api";
import { filings } from "@/lib/data";

export const dynamic = "force-dynamic";

export function GET(request: Request): Response {
  const url = new URL(request.url);
  const source = readSource(url, "just-raised/filings");
  if (!source.ok) return source.response;

  const slug = url.searchParams.get("slug");
  let rows = filings.filings;
  if (slug) {
    const one = rows[slug];
    if (!one) return error(404, "not_found", `no filing for slug ${slug}`);
    rows = { [slug]: one };
  }
  return Response.json(
    { meta: filings.meta, filings: rows, ...(source.value ? { source: source.value } : {}) },
    { headers: HEADERS },
  );
}

export const OPTIONS = options;
