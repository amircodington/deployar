"use client";

import { useCallback, useEffect, useState } from "react";
import { AgentError, api, type Dashboard } from "@/lib/api";
import { fa } from "@/lib/fa";

/** Connections, credit and apps; refreshed on demand (after a save, or when a run finishes). */
export function useDashboard() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    try {
      setData(await api.dashboard());
      setError(null);
    } catch (err) {
      setError(err instanceof AgentError ? err.message : fa.connectionLost);
    }
  }, []);
  useEffect(() => {
    api.dashboard().then(setData, (err) => setError(err instanceof AgentError ? err.message : fa.connectionLost));
  }, []);
  return { data, error, reload };
}
