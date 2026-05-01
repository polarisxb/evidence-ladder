import { useEffect, useRef, useState } from "react";
import type { ScanEvent } from "../types";

export function useWebSocket(taskId: string | undefined) {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!taskId) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/api/v1/scans/ws/${taskId}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      try {
        const data: ScanEvent = JSON.parse(e.data);
        // Stamp the client-side arrival time. Backend events carry no
        // timestamp, and we need something to render "attack has been
        // running for X seconds" badges on the progress page. Clock
        // skew doesn't matter here because all we care about is
        // duration-since-seen inside this browser session.
        data.received_at = Date.now();
        setEvents((prev) => [...prev, data]);
      } catch {
        /* ignore parse errors */
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [taskId]);

  return { events, connected };
}
