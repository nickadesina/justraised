import type { Metadata } from "next";
import { Barlow_Condensed, Inter_Tight } from "next/font/google";

import "./globals.css";

// Self-hosted at build time by next/font; the page makes no font requests.
const sans = Inter_Tight({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const cond = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-cond",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Just Raised",
  description:
    "a16z and speedrun portfolio companies with a recent Form D or investor SPV, newest filing first, next to how many roles they've posted since.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${cond.variable}`}>
      <body>{children}</body>
    </html>
  );
}
