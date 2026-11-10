import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The CSV route reads public/just-raised.csv at request time; make sure the
  // file ships with the serverless function.
  outputFileTracingIncludes: {
    "/api/just-raised.csv": ["./public/just-raised.csv"],
  },
  // Keep the pipeline's Python environment and data out of the function bundles.
  outputFileTracingExcludes: {
    "*": [".venv/**", "data/**", "packages/**", "review/**", "tests/**"],
  },
  poweredByHeader: false,
};

export default nextConfig;
