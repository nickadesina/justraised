// GET /api/collections/just-raised
// Exactly the response shape of the talent network's GET /api/v1/collections/{slug},
// so it can be mounted in their signals group without a translation layer.
// scripts/check_schema.py validates it against their OpenAPI spec.
import { HEADERS, options, readPage, readSource } from "@/lib/api";
import { PAGE_SIZE, collection } from "@/lib/data";

export const dynamic = "force-dynamic";

export function GET(request: Request): Response {
  const url = new URL(request.url);
  const source = readSource(url, "collections/just-raised");
  if (!source.ok) return source.response;
  const page = readPage(url);
  if (!page.ok) return page.response;

  const { members, ...rest } = collection.collection;
  const body = {
    collection: {
      ...rest,
      members: members.slice(page.value * PAGE_SIZE, (page.value + 1) * PAGE_SIZE),
      members_total: members.length,
      page: page.value,
      page_size: PAGE_SIZE,
      total_pages: Math.ceil(members.length / PAGE_SIZE),
    },
    ...(source.value ? { source: source.value } : {}),
  };
  return Response.json(body, { headers: HEADERS });
}

export const OPTIONS = options;
