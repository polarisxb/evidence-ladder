---
name: react-dashboard
description: >-
  React frontend patterns for the AI security testing dashboard. Use when
  creating or modifying frontend pages, components, data views, or UI
  interactions in this repository.
---

# React Dashboard Patterns

Use this together with:

- `$project-conventions` for repository-wide structure and compatibility rules
- `$frontend-design` when the task is primarily about stronger visual direction

## Repository Structure

```text
frontend/
|-- src/
|   |-- api/
|   |-- components/
|   |-- hooks/
|   |-- pages/
|   |-- types/
|   `-- utils/
|-- package.json
|-- tailwind.config.js
|-- tsconfig.json
`-- vite.config.ts
```

## Frontend Rules

- Use function components with TypeScript, not class components.
- Prefer named exports over default exports.
- Keep API calls in `src/api/`.
- Keep shared type definitions in `src/types/`.
- Prefer Tailwind utility classes over one-off CSS.
- Avoid `any` unless there is a narrow, justified interoperability boundary.
- Keep risk color semantics consistent across the UI.

## Risk UI Conventions

Use a stable mapping for security severity and risk-related badges:

- `critical`: red
- `high`: orange
- `medium`: yellow or amber
- `low`: green
- `none`: neutral gray

Do not introduce a conflicting color system for the same concepts on different pages.

## Component Boundaries

- `pages/`: route-level views
- `components/`: reusable UI or domain components
- `api/`: transport wrappers
- `types/`: shared TypeScript contracts
- `utils/`: formatting and lightweight helpers

## Common Patterns

### API Wrapper

```typescript
export async function getScan(taskId: string): Promise<ScanTask> {
  return request<ScanTask>(`/scans/${taskId}`);
}
```

### Named Export Component

```typescript
interface ScanCardProps {
  scan: ScanTask;
  onSelect: (id: string) => void;
}

export function ScanCard({ scan, onSelect }: ScanCardProps) {
  return <div>...</div>;
}
```

### Page Flow

Keep route pages thin:

1. load data through `src/api/`
2. normalize view state locally
3. render reusable child components

Avoid embedding raw fetch logic repeatedly across multiple page components.
