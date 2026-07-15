# RuralFindMe — Frontend Design & Animation Audit

Date: 2026-07-15
Scope: React/TypeScript/Vite frontend (`frontend/src`), read-only. Complements `AUDIT.md` (general codebase audit).

## Resolution Update — 2026-07-15

The findings in this audit have now been addressed in the frontend implementation:

- Motion is governed globally by the in-app preference and the OS preference; layout-triggering animations were replaced with transforms, and shared easing/reveal timings live in `frontend/src/app/animation.ts`.
- Processing progress is announced, progress bars expose their value, and every button has a consistent keyboard focus indicator.
- The unused dark theme was removed so the application consistently preserves its original light palette; success colors, font families, responsive type sizes, and content widths use theme tokens.
- Result layouts and actions stack at narrow widths, large headings use fluid sizes, and long ambiguous-result content wraps safely.
- The explicit processing-stage order no longer relies on object insertion order, and document-row state styling is centralized.
- The unused UI/Figma component kit and empty `globals.css` were removed. Unused DM Sans/DM Mono 300-weight font imports were also removed.
- The muted text combination was checked at **5.19:1**, meeting WCAG AA for normal text. The semantic success pair is **7.78:1**.
- After cleanup, the production CSS bundle fell from about **98.85 KB to 39.26 KB** uncompressed. TypeScript checking and the production build pass.

The sections below are retained as the original audit record and rationale for these changes.

## Structure Summary

- `frontend/src/main.tsx` — trivial bootstrap.
- `frontend/src/bridge.ts` — typed bridge to Qt/PySide; `BackendState.reduced_animation` flows from `app/config/settings.py` through `app/bridge.py:500`.
- `frontend/src/app/App.tsx` — **the entire application lives in one 924-line file**: every screen (Welcome, Upload, Identification, Preparation, Assigned, Status/Exempt/NotSelected, NotFound, Ambiguous, Error) is an inline component here.
- `frontend/src/app/components/ui/*` — a full unmodified shadcn/ui kit (40+ files: accordion, carousel, chart, calendar, sidebar, menubar, command, drawer, etc.) of which only `button` and a few utilities appear actually used.
- `frontend/src/styles/{index,tailwind,fonts,theme}.css` — `globals.css` exists but is **empty (0 bytes)**, dead file.
- Animation-side Python code (`app/animations/*.py`) is **inert legacy Qt-widget code with no call sites** (`confetti.py`, `transitions.py`, `reveal_controller.py`) — safe to ignore or delete; only `sound_effects.py` is wired in. Animation consistency only needs to be assessed within the React layer.

---

## 1. Styling System

| # | File:Line | Problem | Suggested Fix |
|---|-----------|---------|----------------|
| 1 | `frontend/src/styles/theme.css:3-63,65-100` | A complete `.dark` theme variant is defined but **never activated** — no code adds/toggles a `dark` class on `<html>`/`<body>`, and `App.tsx` never reads system/user dark-mode preference. Dead theming code. | Either wire up dark mode (toggle class based on `prefers-color-scheme` or a settings option) or remove the unused `.dark` block to reduce maintenance surface. |
| 2 | `App.tsx` (throughout, e.g. lines 299, 403, 497, 681, 728, 761, 783, 803) | Typography is not centralized: dozens of one-off arbitrary Tailwind sizes (`text-[62px]`, `text-[52px]`, `text-[42px]`, `text-[11px]`, `text-[10px]`, `text-[9px]`) and container widths (`max-w-[640px]`, `max-w-[480px]`, `max-w-[520px]`, …) are used instead of a shared type/spacing scale, despite `theme.css:158-162` already defining generic `h1`/`h2` base styles that end up unused/overridden. | Define a small set of heading/text size tokens (e.g. via Tailwind's `@theme` extension) and replace arbitrary-value classes with them; this also makes future visual tuning a one-place edit instead of a 30+-line search-and-replace. |
| 3 | `App.tsx` (~30+ occurrences, e.g. lines 146, 172, 240, 286, 289, 296, 299, 334, 337, 346, 402-427, 461-517, 601-701) | Font family set via inline `style={{fontFamily:"'DM Mono', monospace"}}` / `'Instrument Serif'` repeated dozens of times instead of Tailwind `font-serif`/`font-mono` utility classes backed by theme tokens. | Add `font-serif`/`font-mono` (or custom `font-display`) utilities mapped to the theme tokens, then replace all inline `style={{fontFamily:...}}` usages — changing the display font currently requires editing dozens of literal strings. |

---

## 2. Animation

**Library:** `motion` (Framer Motion successor) + `canvas-confetti`. No other animation dependency.

| # | File:Line | Problem | Suggested Fix |
|---|-----------|---------|----------------|
| 1 | `App.tsx` — `WelcomeScreen` (283, 295, 306, 328), `UploadScreen` (401), `IdentificationScreen` (495), `DocumentRow` (210-213), `StatusScreen` (726, 740, 744), `NotFoundScreen` (758), `AmbiguousScreen` (780, 787) | The `reduced_animation` setting (wired correctly for `App.tsx:908` top-level transitions and `PreparationScreen`/`AssignedScreen`, lines 557-667) is **not honored** by most other screens' entrance animations. A user who enables "Reducir animaciones" still gets full staggered fade/slide effects everywhere except two screens. | Route all `motion.div` `transition`/`duration` props through a shared helper that reads `reducedAnimation` once (e.g. a `useMotionDuration()` hook or a wrapping `MotionConfig reducedMotion="user"` from Framer Motion itself), instead of manually branching per-screen. |
| 2 | any `frontend/src/styles/*.css` | No `@media (prefers-reduced-motion: reduce)` query exists anywhere — the OS-level accessibility preference is completely ignored; only the app's own (partially-honored) in-app checkbox works. | Add a global `prefers-reduced-motion` CSS rule as a baseline safety net, and/or use Framer Motion's `MotionConfig reducedMotion="user"` which respects the OS setting automatically. |
| 3 | `App.tsx:239` | `animate={{opacity:1, height:"auto"}}` on `DocumentRow`'s expandable details animates `height`, a layout-triggering property, forcing reflow every frame. | Use an `overflow-hidden` wrapper with a `scaleY`/transform animation, or Framer Motion's built-in `layout` prop, instead of animating `height` directly. |
| 4 | `App.tsx:459` | The progress bar animates `width` (`animate={{ width: `${(count/3)*100}%` }}`), also layout-triggering. | Animate `scaleX` with `transform-origin: left` on a full-width element instead — GPU-composited, no reflow. |
| 5 | `App.tsx:213, 295, 328` | The easing curve `[0.22,1,0.36,1]` is retyped as a literal array in 3 separate places instead of a named shared constant — easy to drift out of sync if one is tweaked later. | Extract to a single `const EASE_STANDARD = [0.22,1,0.36,1]` constant and import it everywhere. |
| 6 | `App.tsx:216` | Tailwind class `duration-250` is used, but `250` is not a default Tailwind duration scale value — this class is likely a silent no-op unless a custom `--duration-250` token is defined. | Verify whether this class actually applies anything; if not, replace with a valid Tailwind duration (`duration-200`/`duration-300`) or add the custom token. |
| 7 | `App.tsx:661` (AssignedScreen timers `[600,1500,2400,3200]`) vs. `App.tsx:563` (`PreparationScreen`'s `4300 - (Date.now()-startedAt)`) | Two related choreography constants (final reveal-stage delay and reveal-wait duration) are hardcoded independently in different components, so tuning one without the other can desync the reveal animation from the confetti/payload reveal. | Extract both into one shared constants module (e.g. `revealTiming.ts`) so the relationship between them is explicit and can't silently drift. |
| 8 | `App.tsx:571` | `PreparationScreen`'s stage index is computed via `Object.keys(STAGE_LABELS).indexOf(activeStage)`, relying on **object key insertion order** — fragile if the object literal is ever reordered or transformed. | Replace with an explicit ordered array of stage names (`const STAGE_ORDER = [...] as const`) and use `STAGE_ORDER.indexOf(activeStage)`. |

**Working correctly, no action needed:** top-level `AnimatePresence` screen transitions and `PreparationScreen`/`AssignedScreen` do branch correctly on `reduced_animation`; confetti burst is a single one-shot call gated by the same flag; most animations already target `opacity`/`transform` (GPU-friendly).

---

## 3. Accessibility

| # | File:Line | Problem | Suggested Fix |
|---|-----------|---------|----------------|
| 1 | `App.tsx` — custom buttons at lines 408-423, 463-470, 633-636, 768-769, 805 | These raw `<button>` elements have no `focus-visible` ring styling (unlike the shadcn `ui/button.tsx` which does this correctly at line 8) — keyboard users get only the browser default focus indicator, which may be invisible against custom backgrounds. | Apply the same `focus-visible:ring-*` treatment used in `ui/button.tsx` to all custom buttons in `App.tsx`, or better, actually use the shared `Button` component instead of raw `<button>` tags. |
| 2 | `App.tsx:601` (`STAGE_LABELS`, updates ~every 620ms during `PreparationScreen`) | No `aria-live` region announces the changing stage text — a screen-reader user gets zero feedback that progress is happening. | Wrap the stage label text in an element with `aria-live="polite"` so assistive tech announces each stage change. |
| 3 | `frontend/src/styles/theme.css:8,27` (`--muted-foreground: #6E5F50` on `--background: #F2EBE0`) | This mid-brown-on-linen combination is used for small `text-[10px]`/`text-[11px]` micro-labels throughout `App.tsx` (e.g. lines 146, 232, 244-248, 315, 337, 346, 421, 527) — likely borderline/failing WCAG AA contrast at such small sizes. | Run the actual hex pair through a contrast checker; if failing, darken `--muted-foreground` or reserve it for larger text only. |
| 4 | `App.tsx:625` | `ResultHeader` badge hardcodes stock Tailwind `text-green-800 bg-green-100` instead of a theme token — the only place in the file bypassing the design-token system, and would look inconsistent if dark mode were ever enabled. | Define a semantic "success" token pair in `theme.css` (alongside the existing `--primary`/`--accent` tokens) and use that instead of raw Tailwind palette colors. |

---

## 4. Component Design Consistency

- **Spacing:** Mostly a semi-systematic Tailwind scale (`p-5`, `gap-4`, `mt-3`) mixed with one-off arbitrary pixel values — plausible visually but not enforced by any scale (ties into Styling System #2).
- **Conditional style logic:** Multi-way ternaries building class strings (e.g. `DocumentRow` at `App.tsx:216-225`, repeated in `AssignedScreen`/`StatusScreen`) are duplicated ad hoc across the file rather than centralized via a `cva()` variant helper — the pattern already exists in `ui/button.tsx` (`class-variance-authority`) but isn't reused in the custom app screens, making visual-state bugs easier to introduce unnoticed.
- **List keys:** Generally fine — content-based keys (`key={slot.label}`, `key={record.source_file}-page-{index}`) are used, avoiding animation glitches from index-only keys.
- **z-index/overflow:** Only `z-10`/`z-20`/`z-50` used consistently, no stacking conflicts found. One nested-scroll risk: `AmbiguousScreen`'s `max-h-[330px] overflow-auto` evidence list (line 785) sits inside the outer `overflow-hidden` `Shell` (line 139) — functionally fine as a nested scroll container, but long institution names aren't `truncate`d, so a very long string could look cramped.
- **Loading/empty/error states:** `UploadScreen`/`DocumentRow` has a real designed spinner + error card (lines 415-455) — good, not a gap.

---

## 5. Responsiveness

- The entire 924-line file contains **exactly one** responsive breakpoint (`max-lg:grid-cols-1` on `WelcomeScreen`, line 277). Every other screen assumes a fixed desktop viewport: `StatusScreen`'s 2-column layout (line 724) has no breakpoint fallback, and large fixed font sizes (`text-[62px]`, `text-[52px]`) won't reflow gracefully in a narrower window.
- This may be an accepted tradeoff if the QWebEngineView window has an enforced fixed size at the Qt layer — worth confirming. If the window is user-resizable, `StatusScreen` and the large headline text could overflow or look cramped below ~900-1000px width.
- **Suggested fix (if window is resizable):** add breakpoint variants (`md:grid-cols-1 lg:grid-cols-2`) to the multi-column layouts and cap headline sizes with `clamp()`-style responsive text tokens.

---

## 6. Bundle

| # | Finding | Suggested Fix |
|---|---------|----------------|
| 1 | `frontend/dist/assets` JS bundle ~332 KB, CSS ~98 KB uncompressed. The full shadcn/ui kit (40+ components: accordion, carousel, chart, calendar, sidebar, menubar, drawer, command palette, etc.) ships in `frontend/src/app/components/ui/` but only `button` and a couple of utilities appear to be actually imported by `App.tsx`. | Delete unused `ui/*` component files (or move them to a separate not-bundled reference folder) — reduces both source clutter and the risk that dead code survives tree-shaking. |
| 2 | ~40 font files (Instrument Serif, DM Sans, DM Mono across 2-7 weights each, ~400-450 KB total) are loaded unconditionally via `fonts.css`, but several weights (DM Sans 300/600/700, DM Mono 300/500) don't appear used by any Tailwind font-weight class actually applied in `App.tsx`. | Audit which weights are actually rendered and remove unused `.woff2` files + their `@font-face` declarations. |
| 3 | `motion` + `canvas-confetti` are reasonably sized relative to the amount of choreography actually used across every screen — not a concern. | No action needed. |

---

## Priority Summary

**Do first:**
1. Fix `reduced_animation` so it's actually honored on *every* screen, not just two (Animation #1) — this is a broken accessibility feature promise, not just polish.
2. Add a baseline `prefers-reduced-motion` CSS rule / `MotionConfig reducedMotion="user"` so the OS-level setting works regardless of the in-app toggle (Animation #2).
3. Fix the two layout-triggering animations (`height`, `width`) for animation smoothness (Animation #3, #4).

**Do soon:**
4. Add `focus-visible` styling to custom buttons and an `aria-live` region for stage progress (Accessibility #1, #2) — real keyboard/screen-reader gaps.
5. Verify the muted-foreground contrast ratio at small font sizes (Accessibility #3).
6. Replace `Object.keys(...).indexOf()` stage-order logic with an explicit ordered array (Animation #8) — currently fragile/silently breakable.

**Nice to have:**
7. Centralize typography/spacing tokens and font-family utilities instead of inline arbitrary values (Styling #2, #3).
8. Remove unused shadcn/ui components and unused font weights to trim bundle size (Bundle #1, #2).
9. Either wire up or delete the unused dark theme (Styling #1).
10. Extract shared easing/timing constants (Animation #5, #7).
