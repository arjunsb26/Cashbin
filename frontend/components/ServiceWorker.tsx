"use client";

import { useEffect } from "react";

/** Registers the app shell cache. It never touches API or socket traffic. */
export function ServiceWorker() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    if (window.location.protocol !== "https:" && window.location.hostname !== "localhost") return;
    void navigator.serviceWorker.register("/sw.js").catch(() => {
      // An unregistered worker only costs the offline shell, so there is nothing to say.
    });
  }, []);
  return null;
}
