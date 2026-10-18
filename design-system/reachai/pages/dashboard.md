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

**Identity v2 — paper, ink and stamp** (replaces the generated teal palette; shared with `site/index.html`). All text pairs verified at WCAG AA (lowest 4.68:1).

| Role | Light | Dark |
|------|-------|------|
| Background (paper) | `#F3EFE6` | `#12110E` |
| Surface (card) | `#FBF9F4` | `#1D1C18` |
| Surface deep | `#E9E3D6` | `#1A1915` |
| Text (ink) | `#191813` | `#EEEAE0` |
| Muted text | `#5C574C` | `#A8A295` |
| Rules / borders | ink at 13–14% | ink at 13% |
| Primary buttons | ink fill, paper text | ink fill, paper text |
| Accent (stamp) | `#B8321C` | `#F2735A` |
| Success (sent) | `#2E6A3A` | `#86C994` |
| Warning (pending) | `#8A5A00` | `#E7B65C` |

Typography: Instrument Serif (headings, numbers), Geist (UI text), Geist Mono (labels, pills, metadata).

### Component Overrides

- App shell: left sidebar navigation (collapses to a top tab bar under 860px), hash routes for deep links (`#/approvals`).
- Buttons: pill shape, 44px minimum height, `scale(0.97)` on press (160ms, `cubic-bezier(0.23, 1, 0.32, 1)`); hover effects gated behind `(hover: hover) and (pointer: fine)`; disabled buttons use surface/muted colors.
- Motion (emil-design-eng / animate skills): dialogs enter from `scale(0.96)` + opacity in 220ms; toasts exit faster than they enter; no animation on navigation or other high-frequency actions; reduced motion keeps fades and drops movement.
- Reject asks for confirmation; approve shows the delivery result in a toast.

---

## Page-Specific Components

- No unique components for this page

---

## Recommendations

- Effects: Hover tooltips, chart zoom on click, row highlighting on hover, smooth filter animations, data loading spinners
