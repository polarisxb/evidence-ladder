import { useEffect, useRef, useState } from "react";
import { getEffectiveAppApiKey } from "../api/client";
import type { ScanEvent } from "../types";

export function useWebSocket(taskId: string | undefined) {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!taskId) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    // Stage 1.1d — attach APP_SECRET via Sec-WebSocket-Protocol subprotocol
    // when one is configured. The backend's require_ws_token accepts
    // ``api-key.<token>``; the protocol negotiation channel keeps the
    // token out of URLs / access logs (unlike a ?token= query string).
    // When no key is configured the connection is attempted unauthenticated
    // — this matches HTTP behaviour for local dev (auth_required=false).
    const apiKey = getEffectiveAppApiKey();
    const wsUrl = `${protocol}//${host}/api/v1/scans/ws/${taskId}`;
    const ws = apiKey
      ? new WebSocket(wsUrl, [`api-key.${apiKey}`])
      : new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = (event) => {
      setConnected(false);
      // Code 1008 (Policy Violation) is what require_ws_token uses for
      // missing/invalid tokens. Surface this via the existing
      // ``app-api-auth-required`` event so the App-level handler can
      // prompt the user for their API key — the same flow used for HTTP 401.
      if (event.code === 1008 && typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent("app-api-auth-required", {
            detail: { path: `ws://scans/${taskId}` },
          }),
        );
      }
    };
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
