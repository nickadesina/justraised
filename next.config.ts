import type { NextConfig } from "next";

// Static export for GitHub Pages. A project site lives under /<repo>, so the
// deploy workflow passes that prefix in NEXT_PUBLIC_BASE_PATH (empty locally
// and on a custom domain).
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  trailingSlash: false,
  poweredByHeader: false,
};

export default nextConfig;
