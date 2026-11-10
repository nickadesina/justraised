import type { Metadata } from "next";
import { Barlow_Condensed, Inter_Tight } from "next/font/google";

import { filings } from "@/lib/data";
import { boardIssues } from "@/lib/issues";
import { buildItems } from "@/lib/items";

import "./globals.css";
import Sidebar from "./sidebar";

// Self-hosted at build time by next/font; the page makes no font requests.
const sans = Inter_Tight({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const cond = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-cond",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Just Raised · talent ops",
  description:
    "A talent-team console for the speedrun job board: portfolio companies that just raised, before the roles are posted, and what on the board is worth fixing.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const counts = { raised: buildItems().length, board: boardIssues().flagged };
  return (
    <html lang="en" className={`${sans.variable} ${cond.variable}`}>
      <body>
        <div className="shell">
          <Sidebar counts={counts} updatedAt={filings.meta.generated_at} />
          <div className="workspace">{children}</div>
        </div>
      </body>
    </html>
  );
}
