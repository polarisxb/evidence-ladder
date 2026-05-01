---
name: react-dashboard
description: >-
  React frontend patterns for the AI security testing dashboard. Covers
  project structure, component patterns, TailwindCSS styling, real-time
  updates via WebSocket, and data visualization. Use when creating or
  modifying frontend pages, components, or UI interactions.
---

# React Dashboard Patterns

## Project Structure

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── index.css               # Tailwind directives
│   ├── api/                    # API client
│   │   ├── client.ts           # Axios/fetch wrapper
│   │   ├── scans.ts
│   │   ├── reports.ts
│   │   └── targets.ts
│   ├── components/             # Reusable components
│   │   ├── ui/                 # Base UI components
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── Progress.tsx
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── Layout.tsx
│   │   ├── charts/
│   │   │   ├── RadarChart.tsx
│   │   │   ├── ScoreGauge.tsx
│   │   │   └── RiskDistribution.tsx
│   │   └── scan/
│   │       ├── ScanConfig.tsx
│   │       ├── ScanProgress.tsx
│   │       ├── AttackResultCard.tsx
│   │       └── VulnerabilityList.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── NewScan.tsx
│   │   ├── ScanProgress.tsx
│   │   ├── Report.tsx
│   │   └── Templates.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useScanStatus.ts
│   │   └── useApi.ts
│   ├── types/
│   │   └── index.ts
│   └── utils/
│       ├── risk.ts
│       └── format.ts
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Tech Stack

- **React 18** + TypeScript
- **Vite** for build tooling
- **TailwindCSS** for styling
- **React Router** for navigation
- **Recharts** for data visualization
- **Lucide React** for icons

## Key Patterns

### API Client

```typescript
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

### WebSocket Hook for Real-Time Updates

```typescript
function useWebSocket(taskId: string) {
  const [messages, setMessages] = useState<ScanEvent[]>([]);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/scans/${taskId}`);
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setMessages((prev) => [...prev, data]);
    };
    return () => ws.close();
  }, [taskId]);

  return messages;
}
```

### Router Configuration

```typescript
import { BrowserRouter, Routes, Route } from "react-router-dom";

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/scan/new" element={<NewScan />} />
          <Route path="/scan/:taskId" element={<ScanProgress />} />
          <Route path="/report/:reportId" element={<Report />} />
          <Route path="/templates" element={<Templates />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
```

### Risk Level Styling

```typescript
const riskColors = {
  critical: { bg: "bg-red-500/10", text: "text-red-500", border: "border-red-500" },
  high: { bg: "bg-orange-500/10", text: "text-orange-500", border: "border-orange-500" },
  medium: { bg: "bg-yellow-500/10", text: "text-yellow-500", border: "border-yellow-500" },
  low: { bg: "bg-green-500/10", text: "text-green-500", border: "border-green-500" },
} as const;
```

## Design Guidelines

### Color Palette (Dark Theme)

- Background: `#0a0a0f` (near-black with blue tint)
- Surface: `#12121a`
- Card: `#1a1a2e`
- Border: `#2a2a3e`
- Primary accent: `#6366f1` (indigo)
- Danger: `#ef4444`
- Warning: `#f59e0b`
- Success: `#22c55e`
- Text primary: `#e2e8f0`
- Text secondary: `#94a3b8`

### Typography

Use a monospace-inspired font for the security tool aesthetic:
- Headings: JetBrains Mono or IBM Plex Mono
- Body: Inter or system-ui
- Code/data: JetBrains Mono

### Layout

- Sidebar navigation (collapsible)
- Main content area with max-width constraint
- Security dashboard uses card grid layout
- Reports use full-width scrollable layout

## Page Specifications

### Dashboard
- Security score gauge (0-100, circular)
- Recent scan history table
- Quick-start scan button
- Risk distribution chart

### Scan Progress
- Progress bar with percentage
- Live attack log (scrolling terminal-style)
- Real-time vulnerability count
- Cancel button

### Report
- Overall score with radar chart (per OWASP category)
- Vulnerability cards with expandable details
- Each card shows: attack payload → AI response → analysis → risk level
- Export button (PDF/HTML)
