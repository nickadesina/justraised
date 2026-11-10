import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Just Raised",
  description:
    "a16z and speedrun portfolio companies with a Form D in the last 90 days, ranked by cash raised per open role.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
