"use client";

import { useEffect, useState } from "react";

// The static build prints the run date; in the browser it becomes "updated
// 3 hours ago". The dot is green while the nightly run is current and goes
// grey if it has missed two nights, so a stalled pipeline is visible.
export default function Updated({ at }: { at: string }) {
  const fallback = new Date(at).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const [label, setLabel] = useState(`Updated ${fallback}`);
  const [fresh, setFresh] = useState(true);

  useEffect(() => {
    const hours = (Date.now() - Date.parse(at)) / 3_600_000;
    setFresh(hours < 48);
    if (hours < 1) setLabel("Updated within the hour");
    else if (hours < 24) setLabel(`Updated ${Math.round(hours)} hour${Math.round(hours) === 1 ? "" : "s"} ago`);
    else setLabel(`Updated ${fallback}`);
  }, [at, fallback]);

  return (
    <span className={`live ${fresh ? "" : "stale"}`}>
      <span className="dot" aria-hidden="true" />
      {label} · refreshed nightly from SEC EDGAR
    </span>
  );
}
