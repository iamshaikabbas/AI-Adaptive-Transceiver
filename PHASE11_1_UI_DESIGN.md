# PHASE 11.1 — UI DESIGN DOCUMENT

## 1. Objective

Redesign the entire AI-Adaptive-Transceiver frontend into a professional engineering
monitoring and control console. Replace the default AI-dashboard aesthetic with a
white/black/gold palette and dense, data-first information layout suitable for a
wireless communication engineering tool.

No backend logic, data, algorithms, MATLAB, or Phase 3/4/5/6/7 functionality was
modified. This phase is purely visual/structural on the frontend.

---

## 2. Design Philosophy

The application is a **digital twin and performance console** for an adaptive wireless
transceiver. It is not a marketing dashboard or an AI showcase. The UI must communicate
technical information at density and clarity appropriate for engineers who work with
wireless communication systems.

Core principles:
- **Data density over whitespace.** Engineering consoles present many parameters
  simultaneously; the layout favors compact tables, monospace numerics, and
  compact charts over large cards with padding.
- **Minimal chrome.** No decorative gradients, glow effects, rounded containers,
  or glassmorphism. Corners are 0-2px. Borders are 1px solid. Shadows are
  absent.
- **Gold as accent, not identity.** Gold is used sparingly (~10% of surface area)
  for active indicators, section headers, and status highlights. The dominant
  palette is white and black.
- **AI is a subsystem.** The Phase 3 AI policy is presented as one decision
  engine among other components (oracle, fixed strategies). It does not define
  the visual identity.

---

## 3. Engineering-Console Visual Direction

The visual direction draws from industrial network monitoring tools (Grafana,
Wireshark, network operations dashboards) and instrumentation front panels.

Characteristics:
- Flat design with zero depth effects (no shadows, no elevation, no blur).
- High contrast black text on white surfaces for readability under any
  lighting condition.
- Compact information density: 2-4px border radius, 11-13px body text,
  10-11px labels.
- Monospace numerics for all quantitative values to ensure alignment in
  tabular data.
- Status communication via color dot indicators (gold = active/alert,
  gray = idle, black = inactive).
- Section headers are 11px uppercase with wide letter-spacing in gold.

---

## 4. Color System

The palette is restricted to white, black, gold, and neutral grays. No other
hues are used in any component or page.

### 4.1 Primary Colors

| Token              | Hex       | Usage                                  |
|--------------------|-----------|----------------------------------------|
| `--color-surface`  | `#FFFFFF` | Main background, panels                |
| `--color-black`    | `#111111` | Primary text, active buttons, SVG paths|
| `--color-dark-black` | `#000000` | Header background, pressed states     |
| `--color-gold`     | `#C9A227` | Section headers, active indicators, highlights |
| `--color-gold-dark`| `#A8830F` | Gold hover state                       |
| `--color-gold-light`| `#E7D79A` | Header secondary text                 |

### 4.2 Neutral Grays

| Token                   | Hex       | Usage                              |
|-------------------------|-----------|------------------------------------|
| `--color-surface-alt`   | `#F7F7F5` | Alternate surface, chart areas     |
| `--color-surface-raised`| `#EEEEEE` | Subtle depth distinction           |
| `--color-border`        | `#D9D9D9` | Primary borders                    |
| `--color-border-subtle` | `#EEEEEE` | Table row separators               |
| `--color-text-primary`  | `#111111` | Headings                           |
| `--color-text-secondary`| `#333333` | Body text, descriptions            |
| `--color-text-muted`    | `#666666` | Labels, meta information           |

### 4.3 Semantic Colors

| Token                | Hex       | Usage                              |
|----------------------|-----------|------------------------------------|
| `--color-active`     | `#C9A227` | Active nav item, running indicator |
| `--color-active-light`| `#F5EFC5`| Warning banners, OOD backgrounds   |
| `--color-inactive`   | `#999999` | Idle/offline indicators            |

### 4.4 Explicitly Excluded

The following color families are **not used anywhere** in the redesign:
- Blue (#2563eb, #3B82F6, #60A5FA)
- Green (#10B981, #22C55E, #34D399)
- Red (#EF4444, #F87171)
- Purple (#8B5CF6, #A78BFA)
- Cyan (#06B6D4, #22D3EE)
- Orange (#F97316)
- Pink (#EC4899)
- Any neon, glow, gradient, or glassmorphism effect

---

## 5. Typography

### Font Stacks

```css
--font-sans: "Inter", "SF Mono", "Consolas", system-ui, -apple-system, sans-serif;
--font-mono: "SF Mono", "Consolas", "Liberation Mono", monospace;
```

### Type Scale

| Element               | Size  | Weight    | Font     | Color          |
|-----------------------|-------|-----------|----------|----------------|
| Page title            | 18px  | 600       | sans     | `#111111`      |
| Section header        | 11px  | 600       | sans     | `#C9A227` gold |
| Table header          | 11px  | 500       | sans     | `#666666`      |
| Body / table cell     | 12-13px| 400      | sans     | `#111111`      |
| Label                 | 11px  | 400       | sans     | `#666666`      |
| Monospace data value  | 12px  | 500       | mono     | `#111111`      |
| Status badge          | 11px  | 600       | mono     | gold or black  |
| Navigation item       | 13px  | 400/500   | sans     | `#333` / `#111`|
| Version footer        | 10px  | 400       | mono     | `#666666`      |

---

## 6. Layout Architecture

### App Shell (`App.tsx`)

```
+------------------------------------------+
|  Header (h-14, dark-black background)    |
+------+-----------------------------------+
|      |                                   |
| Side |    Main Content Area              |
| bar  |    (bg: surface-alt #F7F7F5)     |
| w-44 |                                   |
|      |                                   |
+------+-----------------------------------+
```

- Header is fixed at the top, full width.
- Sidebar is fixed width (176px / `w-44`), hidden on screens < 768px.
- Main content area scrolls vertically within the remaining space.
- All content pages use `max-w-[1400px]` or `max-w-5xl` centered containers.

---

## 7. Navigation Structure

The sidebar is organized into four functional sections:

```
MONITOR
  Overview
  Digital Twin

EVALUATION
  Custom Eval

ANALYSIS
  Results

SYSTEM
  About
```

### Sidebar Behavior

- Section labels: 10px uppercase, gold color, wide letter-spacing (`tracking-widest`).
- Active item: left 2px gold border, black text, white background.
- Inactive item: transparent left border, `text-secondary`, hover transitions to
  black text with `surface-alt` background.
- Footer: `CONSOLE v11.1` in 10px monospace gray.

---

## 8. Digital Twin Page Design

The Digital Twin page is the primary operational view. It uses a **3-column layout**
at `lg` breakpoint and stacks vertically below that.

```
+------------+-----------------------+------------+
| Left (3)   | Center (6)            | Right (3)  |
|            |                       |            |
| Simulation | Signal Path SVG       | Live       |
| Controls   | Waveform Selection    | Charts     |
|            | Waveform Comparison   | (BER,      |
| Operating  | Oracle Reference      |  Thru,     |
| Conditions | Timeline              |  ACS, CQI) |
|            | Waveform Usage Bar    |            |
| Current    |                       |            |
| Metrics    |                       |            |
+------------+-----------------------+------------+
```

### Left Column (3/12)

- **Simulation Control** — Scenario, mode, strategy, policy selectors; START/PAUSE/
  RESUME/STOP/RESET buttons; frame counter.
- **Operating Conditions** — Table: environment, speed, SNR, Doppler, channel profile,
  modulation, current frame.
- **Current Metrics** — Table: BER, throughput, CQI, ACS, waveform, oracle.

### Center Column (6/12)

- **Signal Path** — SVG block diagram: TX → Channel → RX with parameter annotations
  and SNR indicator bars.
- **Waveform Selection** — Selected waveform, policy, confidence, ACS values, reason.
- **Waveform Comparison** — Side-by-side OTFS vs ODDM metric table.
- **Oracle Reference** — Selected vs oracle waveform, agreement, ACS regret.
- **Timeline** — Frame progress bar with gold switch markers.
- **Waveform Usage** — Segmented bar showing OTFS (gold) / ODDM (black) proportions.

### Right Column (3/12)

- **Live Charts** — 2x2 grid of sparkline charts: BER, Throughput, ACS, CQI.
  Gold primary line, black secondary. Auto-scrolling to last 60 frames.

---

## 9. Custom Evaluation Design

Full-page form for evaluating user-defined operating points against the frozen
dataset and Phase 3 regression models.

### Layout

```
+----------------------------------------------+
|  Custom Operating Point                      |
|  MODEL-BASED EVALUATION                      |
+----------------------------------------------+
|  Input Parameters (3-column grid)            |
|  [Environment] [Speed] [SNR]                 |
|  [Channel] [Modulation] [Detector]           |
|  [EVALUATE button]                           |
+----------------------------------------------+
|  Model Coverage                              |
|  Coverage: EXACT | Confidence: HIGH          |
+----------------------------------------------+
|  Predicted Performance                       |
|  +-------------+  +-------------+            |
|  | OTFS        |  | ODDM        |            |
|  | (detector)  |  | (detector)  |            |
|  | Metric table|  | Metric table|            |
|  +-------------+  +-------------+            |
+----------------------------------------------+
|  Waveform Selection                          |
|  Policy | Selected | Objective | ACS values  |
+----------------------------------------------+
|  Nearest Validated Operating Points          |
|  (sortable table of neighbors)               |
+----------------------------------------------+
|  Disclaimer                                  |
+----------------------------------------------+
```

### Styling

- Input selectors: white background, 1px `#D9D9D9` border, gold focus ring.
- EVALUATE button: black background, white text, no border radius.
- Coverage badge: `EXACT`/`COVERED`/`NEAR BOUNDARY` in black border; `OOD` in gold border.
- Prediction tables: metric name (gray), value (black monospace), uncertainty (gray),
  p10-p90 range (gray, smaller text).
- Warning banners: gold border, `active-light` background, black text.

---

## 10. Waveform Comparison

A compact table comparing OTFS and ODDM waveform predictions side by side.

| Metric | OTFS | ODDM |
|--------|------|------|
| ACS    | 0.xxxx | 0.xxxx |

- Column header: 11px, gray, monospace.
- Selected waveform row: `active-light` (#F5EFC5) background highlight.
- Values: 12px black monospace, right-aligned.

---

## 11. Waveform Selection (formerly AIDecisionPanel)

Displays the output of the Phase 3 AI policy decision engine.

### Layout

| Field       | Value         |
|-------------|---------------|
| Selected    | OTFS / ODDM  |
| Policy      | Phase 3      |
| Confidence  | xx.x%        |
| ACS (OTFS)  | 0.xxxx       |
| ACS (ODDM)  | 0.xxxx       |

- Reason text: monospace, `surface-alt` background, 1px border.
- Switch indicator: gold border badge with `SWITCH` label when a waveform
  transition occurs on the current frame.

---

## 12. Signal-Path Visualization

An SVG block diagram representing the transceiver signal path:

```
[ TX ] --- → [ Channel ] --- → [ RX ]
       dashed    block      dashed
       black     black      black
```

### Elements

- **TX block**: White fill, gray border, "TX" / "Transmitter" labels.
- **Channel block**: White fill, gray border. Contains environment name,
  channel profile, modulation, speed, Doppler, SNR.
- **SNR indicator**: 5-segment bar, filled segments in black, unfilled in gray.
- **RX block**: White fill, gray border, "RX" / "Receiver" labels.
- **Signal paths**: 1px dashed black lines connecting blocks.
- **Active waveform**: Gold text centered below the channel block.

All SVG colors are restricted to black (`#111111`), gray (`#666666`, `#999999`,
`#D9D9D9`), and gold (`#C9A227`). No blue or colored paths.

---

## 13. Charts

Four sparkline charts displayed in a 2x2 grid using Recharts.

### Chart Styling

| Property       | Value                                   |
|----------------|-----------------------------------------|
| Primary line   | `#C9A227` gold, 1.5px stroke           |
| Secondary line | `#111111` black, 1.5px stroke           |
| Grid lines     | None (hidden)                           |
| Axes           | None (hidden)                           |
| Tooltip        | White background, 1px `#D9D9D9` border, 2px radius, 11px text |
| Chart height   | 56px (h-14)                             |
| Animation      | Disabled (`isAnimationActive={false}`)  |
| Data window    | Last 60 frames                          |

### Charts Displayed

| Chart      | Data Key          | Format         | Color    |
|------------|-------------------|----------------|----------|
| BER        | `BER`             | 4 decimal      | Gold     |
| Throughput | `throughput_bps`  | kbps / 1       | Black    |
| ACS        | `ACS`             | 4 decimal      | Gold     |
| CQI        | `CQI`             | integer        | Black    |

---

## 14. Tables

All data tables follow a consistent pattern:

- No `<table>` border attributes; styling via CSS.
- Header row: 11px, gray (`#666666`), font-weight 500, bottom border.
- Data rows: 12px, black text, bottom 1px `#EEEEEE` separator.
- Last row: no bottom border.
- Numeric values: right-aligned, monospace font, font-weight 500.
- Labels: left-aligned, gray.
- Selected/active row: `active-light` background (`#F5EFC5`).

---

## 15. Status Indicators

### Color Coding

| State       | Dot Color      | Text Color    |
|-------------|----------------|---------------|
| Running     | Gold `#C9A227` | White         |
| Paused      | Gold light     | White         |
| Connected   | Gold `#C9A227` | White         |
| Disconnected| Gray `#999`    | White 50%     |
| Idle/Stopped| Gray `#999`    | White 70%     |

### Header Status Bar

- Background: `#000000` (dark-black).
- Status dots: 6px rounded circles.
- Labels: 11px monospace, white.
- Scenario and frame counters: `SCN A`, `FRM 12/100` format.

---

## 16. Event Log

The waveform usage switching bar serves as the event log indicator:

- Segmented horizontal bar showing OTFS (gold) and ODDM (black) proportions.
- Switch count displayed as `SW: N` in monospace.
- Legend: gold square = OTFS (count), black square = ODDM (count).
- Segment hover reveals frame range in tooltip.

The timeline bar above it shows:
- Black progress fill from left to right.
- Gold 2px vertical markers at each switch point.
- Legend: gold dot = Switch, black line = Progress.

---

## 17. OOD / Invalid-Input Presentation

### Out-of-Distribution Detection

When a custom evaluation falls outside the model domain:

- Coverage badge: `OUTSIDE COVERAGE` in gold border, gold text.
- Confidence badge: `UNAVAILABLE` in gold border, gold text.
- Warning banners: gold border, `active-light` (#F5EFC5) background.
- No fabricated metric values are displayed; cells show "N/A".

### Invalid Input

- Error messages: gold border, `active-light` background, black monospace text.
- Form validation errors appear inline or as top-of-page banners.
- Backend rejection messages (e.g., "NaN speed rejected") are displayed
  verbatim in the same error banner style.

---

## 18. Responsive Behavior

| Breakpoint  | Layout                                              |
|-------------|-----------------------------------------------------|
| `>= 1024px` | 3-column Digital Twin (3/6/3 grid)                  |
| `768-1023px`| Sidebar hidden, single-column stacked               |
| `< 768px`   | Sidebar hidden, all content single column, full width |

- Tables use `overflow-x-auto` for horizontal scroll on narrow screens.
- Chart grid collapses to single column below `md`.
- Custom Evaluation form grid collapses from 3-column to 1-column.
- All containers use `p-4` to `p-6` padding, sufficient for touch targets.

---

## 19. Accessibility Considerations

- **Color contrast**: Black text (#111111) on white (#FFFFFF) provides a
  contrast ratio of approximately 18:1, exceeding WCAG AAA requirements.
  Gold text (#C9A227) on white provides approximately 3:1 for decorative
  elements; gold is not used for critical information alone.
- **Monospace numerics**: All quantitative data uses monospace fonts, enabling
  easy scanning and comparison of aligned columns.
- **Form labels**: Every input has an associated `<label>` element.
- **Disabled states**: Disabled buttons and inputs have `opacity: 0.4` and
  `cursor: not-allowed`.
- **Keyboard navigation**: Standard browser focus behavior; gold `focus:ring`
  on interactive elements.
- **No auto-playing animations**: Chart animation is disabled; all transitions
  are CSS `transition-all duration-300`.

---

## 20. Removed AI-Dashboard Patterns

The following visual patterns from the original AI-dashboard aesthetic were
explicitly removed:

| Removed Pattern                  | Replacement                        |
|----------------------------------|------------------------------------|
| Blue gradient header             | Solid black header bar             |
| Purple/pink accent cards         | White panels with 1px gray borders |
| Rounded containers (8-12px)      | Sharp corners (0-2px)              |
| Box shadows                      | None (flat design)                 |
| Glassmorphism / backdrop-blur    | None                               |
| Colored status badges (green/red)| Gold/black monospace badges         |
| "AI Powered" / "Smart AI" labels | "Phase 3 AI Policy" / "Waveform Selection" |
| Neon glow effects                | None                               |
| Gradient buttons                 | Solid black or white               |
| Large padded metric cards        | Compact table rows                 |
| Animated loading spinners        | Static "Awaiting data" text        |
| "AI Decision" heading            | "Waveform Selection" heading       |

---

## 21. Component/Page Files Redesigned

| File                              | Lines | Status       |
|-----------------------------------|-------|--------------|
| `src/index.css`                   | 59    | Redesigned   |
| `src/components/Header.tsx`       | 65    | Redesigned   |
| `src/components/Sidebar.tsx`      | 69    | Redesigned   |
| `src/components/SimulationControls.tsx` | ~80 | Redesigned |
| `src/components/AIDecisionPanel.tsx` | ~50 | Redesigned  |
| `src/components/WaveformComparison.tsx` | ~40 | Redesigned |
| `src/components/OracleComparison.tsx` | ~45 | Redesigned  |
| `src/components/SwitchingBar.tsx` | ~65   | Redesigned   |
| `src/components/Timeline.tsx`     | ~53   | Redesigned   |
| `src/components/LiveCharts.tsx`   | ~80   | Redesigned   |
| `src/components/DigitalTwinViz.tsx` | ~70 | Redesigned   |
| `src/pages/Overview.tsx`          | ~90   | Redesigned   |
| `src/pages/DigitalTwinPage.tsx`   | ~180  | Redesigned   |
| `src/pages/CustomEvaluation.tsx`  | ~240  | Redesigned   |
| `src/pages/Analysis.tsx`          | ~110  | Redesigned   |
| `src/pages/About.tsx`             | ~120  | Redesigned   |

**Total: 16 files redesigned.** Zero new files created. Zero backend files modified.

---

## 22. Functional Behavior Preserved

All existing functionality was preserved without modification:

| Feature                           | Preserved |
|-----------------------------------|-----------|
| START / PAUSE / RESUME / STOP / RESET | Yes   |
| Scenario selection (A-R)          | Yes       |
| Mode selection (FAST / FULL)      | Yes       |
| Strategy selection                | Yes       |
| Policy selection                  | Yes       |
| Real-time WebSocket updates       | Yes       |
| Historical frame graphs (Recharts)| Yes       |
| Custom Evaluation form            | Yes       |
| Custom Evaluation API integration | Yes       |
| Waveform switching visualization  | Yes       |
| Oracle comparison                 | Yes       |
| Signal-path SVG diagram           | Yes       |
| Phase 7 analysis graph browser    | Yes       |
| Digital Twin page 3-column layout | Yes       |
| Connection status in header       | Yes       |
| Scenario/frame counters in header | Yes       |

---

## 23. Validation Results

```
PHASE 11 VALIDATION SUITE  (40 tests)
======================================================================

  40/40 passed  |  0 failed

  Dataset Integrity:     5/5 PASS
  Model Integrity:       4/4 PASS
  Exact Lookup:          3/3 PASS
  Regression:            4/4 PASS
  Neighborhood:          4/4 PASS
  Uncertainty:           3/3 PASS
  OOD Detection:         5/5 PASS
  AI Decision:           3/3 PASS
  API:                   4/4 PASS
  Edge Cases:            5/5 PASS
```

---

## 24. Build Result

```
✓ TypeScript compilation: 0 errors
✓ Vite build: 383ms
✓ dist/index.html:        0.68 kB  (gzip: 0.39 kB)
✓ dist/assets/index.css: 17.62 kB  (gzip:  4.43 kB)
✓ dist/assets/index.js: 587.62 kB  (gzip: 171.95 kB)
```

---

## 25. Dataset Integrity

```
File: final_dataset.csv
Checksum (MD5): faa877a248c0f599a87f21dabf4df358
Rows: 2,336
Columns: 82
Scenarios: 18 (A-R)
Strategies: 4 (ai_adaptive, fixed_oddm, fixed_otfs, oracle)
```

The dataset was **not modified** during Phase 11.1. The checksum was verified
after the UI redesign and matches the Phase 6 baseline.

---

## 26. Known Limitations

1. **Sidebar hidden on mobile.** Navigation on screens < 768px requires the
   sidebar to be hidden. No hamburger menu or mobile drawer was implemented.
   Users on mobile devices cannot access navigation without viewport resizing.

2. **No dark mode.** The console is white-background only. A dark mode variant
   would require a separate token set and was not in scope.

3. **Gold text contrast.** Gold (#C9A227) on white (#FFFFFF) achieves
   approximately 3:1 contrast ratio. While acceptable for decorative/accidental
   text, it does not meet WCAG AA (4.5:1) for body text. Gold is used only
   for section headers and accent indicators, not for primary data display.

4. **Chart data window fixed at 60 frames.** Older frames are discarded from
   the sparkline view. No zoom or pan capability was added.

5. **No keyboard shortcuts.** Standard tab navigation works, but no custom
   keyboard shortcuts (e.g., Space for pause, Enter for start) were added.

6. **Scrollbar styling is WebKit-only.** Custom scrollbar styles apply to
   Chrome/Safari/Electron. Firefox and Edge use default scrollbars.

---

## 27. Final Design Rationale

The redesign transforms the application from a generic AI-dashboard into a
**wireless communication engineering console**. The key decisions:

- **White/black/gold** provides sufficient contrast for dense data display while
  distinguishing the application from consumer-facing dashboards that typically
  use blue or purple palettes.

- **Table-first data display** matches how engineers consume performance data:
  aligned numeric columns, monospace values, and compact rows rather than large
  card layouts with single values.

- **Gold accent** is reserved exclusively for the section headers, active
  navigation indicators, status dots, and warning banners. This limits its
  surface area to approximately 10% of the viewport, preventing it from
  dominating the visual hierarchy.

- **AI policy is a subsystem.** By labeling the AI panel as "Waveform Selection"
  and presenting it alongside the oracle reference and fixed-strategy comparison,
  the UI treats machine learning as one tool in the decision pipeline rather
  than the identity of the application.

- **No decorative effects.** Every pixel in the console communicates information.
  Gradients, shadows, blur, and glow add visual noise without improving data
  comprehension. Their removal increases information density and reduces
  cognitive load.

The result is a console that communicates its purpose — monitoring and controlling
an adaptive transceiver digital twin — through its visual language, not through
labels or branding.

---

**PHASE 11.1 COMPLETE**
