import type { Metadata, Viewport } from "next";
import { Archivo, Noto_Serif_JP } from "next/font/google";

import "./globals.css";

// Display: a black-weight mincho for title-card lettering. UI: Archivo's width
// axis, condensed for readouts and labels, normal width for reading.
const display = Noto_Serif_JP({
  weight: "900",
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display",
});

const ui = Archivo({
  subsets: ["latin"],
  axes: ["wdth"],
  display: "swap",
  variable: "--font-ui",
});

export const metadata: Metadata = {
  title: "Just Raised",
  description:
    "a16z and speedrun portfolio companies with a Form D in the last 90 days, ranked by cash raised per open role.",
};

export const viewport: Viewport = {
  themeColor: "#f5f5f3",
  colorScheme: "light",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${ui.variable}`}>
      <body>{children}</body>
    </html>
  );
}
