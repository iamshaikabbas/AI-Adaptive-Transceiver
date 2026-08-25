# PHASE 10 — UI Design Documentation

## Design Philosophy

Clean, minimal, professional engineering application. Not a generic AI dashboard.

Inspired by modern engineering software and research laboratory interfaces.

## Color System

| Role | Color | Tailwind |
|---|---|---|
| Background (main) | White | `bg-white` / `bg-surface` |
| Background (secondary) | Light gray | `bg-gray-50` / `bg-surface-alt` |
| Text (primary) | Dark charcoal | `text-gray-900` / `text-text-primary` |
| Text (secondary) | Medium gray | `text-gray-600` / `text-text-secondary` |
| Text (muted) | Light gray | `text-gray-400` / `text-text-muted` |
| Borders | Soft gray | `border-gray-200` / `border-border` |
| Accent (primary) | Blue | `#2563eb` / `bg-accent` |
| Success | Green | `#16a34a` / `bg-success` |
| Warning | Amber | `#d97706` / `bg-warning` |
| Error | Red | `#dc2626` / `bg-error` |
| Inactive | Gray | `#9ca3af` / `bg-inactive` |

## Typography

- Font: Inter (Google Fonts), fallback to system-ui
- Headings: 14-18px, semibold
- Labels: 12px, regular/medium
- Metric values: 13-14px, semibold, monospace for numeric values

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│ Header: Project name · Status · Connection                   │
├───────────────┬──────────────────────────────────────────────┤
│ Sidebar       │ Main Content                                 │
│               │                                              │
│ Overview      │ (varies by page)                             │
│ Digital Twin  │                                              │
│ Analysis      │                                              │
│ About         │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

## Pages

### Overview
- Project name and subtitle
- Brief system description
- System status indicators
- Final evaluation reference metrics (historical)
- Architecture diagram
- Key metrics definitions

### Digital Twin (primary)
- 3-column layout on large screens
- Left: Simulation controls, Environment panel, Performance metrics
- Center: Channel model SVG, AI decision, Waveform comparison, Oracle reference, Timeline, Switching bar
- Right: Live charts (BER, Throughput, ACS, CQI)

### Analysis
- Category filter buttons
- Graph grid with thumbnails
- Click to expand full-size image
- Description and interpretation on expand

### About
- Project description
- Digital twin explanation
- Waveform comparison
- AI policy details
- Evaluation metrics
- Architecture diagram
- Limitations
- Technology stack

## Component Design Principles

1. **No excessive cards** — Use sections with subtle separators
2. **Compact data tables** — Key-value rows for environment and performance data
3. **Minimal color** — Only use color for semantic meaning (active, success, warning, error)
4. **No animations** — Only chart transitions and status indicators
5. **No gradients** — Solid colors only
6. **No glassmorphism** — Clean solid backgrounds with thin borders
7. **Readable at 1366×768** — Compact but not cramped
