# Dashboard Page Overrides

> **PROJECT:** ReachAI
> **Generated:** 2026-10-18 16:51:45
> **Page Type:** Dashboard / Data View

> ⚠️ **IMPORTANT:** Rules in this file **override** the Master file (`design-system/MASTER.md`).
> Only deviations from the Master are documented here. For all other rules, refer to the Master.

---

## Page-Specific Rules

### Layout Overrides

- **Max Width:** 1400px or full-width
- **Grid:** 12-column grid for data flexibility

### Spacing Overrides

- **Content Density:** High — optimize for information display

### Typography Overrides

- No overrides — use Master typography

### Color Overrides

Adjusted for WCAG AA contrast with white or dark text on filled controls (implemented in `src/reachai/static/index.html`):

| Role | Light | Dark | Why |
|------|-------|------|-----|
| Primary (buttons, active chip) | `#0F766E` on `#FFFFFF` | `#2DD4BF` on `#042F2E` | Master `#0D9488` with white text is below 4.5:1 |
| Accent / CTA | `#C2410C` on `#FFFFFF` | `#FB923C` on `#1C0A00` | Master `#EA580C` with white text is below 4.5:1 |
| Border | `#CDEDE7` | `#24413C` | Master `#99F6E4` is too loud for dense tables |
| Destructive | `#B91C1C` | `#F87171` | Outline button text needs 4.5:1 on surface |
| Background / Surface | `#F0FDFA` / `#FFFFFF` | `#0B1514` / `#11201E` | Dark mode derived from Master hues |

Status pills: pending = amber, approved/sending = primary-soft, sent/contacted = green, rejected = red.

### Component Overrides

- App shell: left sidebar navigation (collapses to a top tab bar under 860px), hash routes for deep links (`#/approvals`).
- Buttons: 44px minimum height; disabled buttons use surface/muted colors instead of opacity so they read as disabled on bright fills.
- Reject asks for confirmation; approve shows the delivery result in a toast.

---

## Page-Specific Components

- No unique components for this page

---

## Recommendations

- Effects: Hover tooltips, chart zoom on click, row highlighting on hover, smooth filter animations, data loading spinners
