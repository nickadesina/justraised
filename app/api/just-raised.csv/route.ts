// GET /api/just-raised.csv: every column, for a spreadsheet.
import { readFile } from "node:fs/promises";
import path from "node:path";

import { HEADERS, options, readSource } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  const source = readSource(new URL(request.url), "just-raised.csv");
  if (!source.ok) return source.response;
  const csv = await readFile(path.join(process.cwd(), "public", "just-raised.csv"), "utf8");
  return new Response(csv, {
    headers: {
      ...HEADERS,
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": 'inline; filename="just-raised.csv"',
    },
  });
}

export const OPTIONS = options;
