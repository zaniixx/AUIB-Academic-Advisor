# AUIB Academic Advisor: design system

The rules the web app's screens follow. The code is the source of truth for values:
tokens live in [web/src/app/globals.css](../../web/src/app/globals.css), shared components in
[web/src/components/ui.tsx](../../web/src/components/ui.tsx) (plus
[ui-client.tsx](../../web/src/components/ui-client.tsx) for the ones with state), and icons in
[web/src/components/icons.tsx](../../web/src/components/icons.tsx). This page explains the decisions
so a change keeps the app consistent.

## Who it is for

- **Students**, most of them not technical, often on a phone. Each screen answers one question
  ("what do I take next?", "when do I graduate?") before offering detail.
- **Advisors**, who mostly see the printed plan ([AdvisorDocument](../../web/src/components/plan/AdvisorDocument.tsx)).
- **Reviewers** (CS department, IT). The app adds no UI packages: no component kit, no icon
  font, no animation library.

## Brand

Taken from AUIB's public site (auib.edu.iq) on 2026-10-08.

| Token | Light | Use |
| --- | --- | --- |
| `--brand-primary` | `#9C213F` maroon | Primary buttons, links, selection, the active tab underline |
| `--brand-ink` | `#273237` slate | Header, footer, dark bands, the selected tab |
| `--brand-accent` | `#79726E` warm grey | Quiet accents such as summer-term borders |
| Font | Ubuntu (next/font, self-hosted) | Everything; Ubuntu Arabic is reserved for an Arabic interface |

- The app mark is a maroon square with a graduation-cap icon. **The AUIB logo is not used**
  until AUIB communications approves it in writing.
- Status colours (done, in progress, planned, blocked, warning) stay clearly apart from the
  maroon. A status is always shown with an icon or a word as well, never by colour alone.
- Dark mode redefines every colour token under `prefers-color-scheme: dark`. Components use
  tokens, never raw hex values, so both themes stay in step. The printed plan always uses the
  light "paper" tokens.

## Layout and type

- Content width is `max-w-6xl` with a 16px side gutter. No screen scrolls sideways at 380px
  (the E2E tests check this on every step).
- Spacing follows a 4px rhythm. Sections are 24–40px apart (`space-y-6` to `space-y-10`), and
  cards pad 20–24px.
- Body text is at least 14px (`text-sm`) in dense lists and 16px in prose. Headings use
  `text-wrap: balance`.
- Radii: cards 16px, fields 12px, buttons fully rounded (AUIB's button shape).
- Elevation has three steps: `shadow-soft` at rest, `shadow-card` for raised panels and hover,
  and `shadow-float` for dialogs and the floating "Updating your plan…" notice.

## Components

| Component | Notes |
| --- | --- |
| `Button`, `ButtonLink` | Variants: primary, secondary, ghost, quiet, danger. Sizes: sm (36px), md (44px), lg (48px). Pressing scales to 97%. |
| `Select`, `FIELD` | Native controls with the shared field style, so the keyboard and screen readers behave as usual. |
| `Card`, `PageHeader`, `IconBadge`, `EmptyState` | Page and section structure. |
| `StatusBadge`, `Badge` | A status always has an icon and a word. |
| `ProgressBar`, `ProgressRing` | Completed (green), in progress (blue), planned (light purple). The ring draws itself once. |
| `CountUp` | A number counts up when it first appears. It is used only for the headline figures (degree %, CGPA). |
| `Tabs`, `TabPanel` | WAI-ARIA tabs. Arrow keys, Home and End move between tabs. |
| `Segmented`, `Switch` | Radio groups and a checkbox (`role="switch"`) drawn as pills. |
| `Disclosure`, `ShowMore` | Progressive disclosure for details and long lists. |
| `Dialog` | Native `<dialog>` used as a modal: focus is trapped and Escape closes it. |
| `Skeleton` | Loading placeholders in the final shape, so nothing jumps when data arrives. |

## Icons

- One in-house set: 24px grid, 2px stroke, round ends, outline style. Status glyphs are a
  separate small set on a 16px grid.
- Icons beside text are decorative (`aria-hidden`). An icon-only button carries an
  `aria-label` (for example "More about CSC 231", "Close").
- No emoji as icons.

## Motion

Motion explains a change: something arrived, something opened, something is loading. It is
never decoration for its own sake.

- **Tokens:** `--ease-out` (arrivals), `--ease-in` (exits), `--ease-spring` (small "pop"
  confirmations), and durations of 150, 240 and 480ms. Exits run faster than entrances.
- **Properties:** only `transform` and `opacity` are animated (plus the progress ring's stroke).
  Layout properties are never animated.
- **One or two moments per view.** Home: the hero text staggers in and the example plan floats.
  Plan page: the progress ring draws, the CGPA counts up, and the term cards stagger in at 60ms
  apart. Switching steps or tabs fades the new content up 14px.
- **Fill mode:** entrances fill `backwards` only. Once finished they release the element, so hover
  lifts work and `position: fixed` children are not trapped.
- **Reduced motion:** with `prefers-reduced-motion: reduce`, every animation and transition is
  switched off, smooth scrolling stops, and numbers show their final value at once. The E2E tests
  run in this mode.

## Patterns by page

- **Home:** a promise, one main action ("Start planning"), and proof (an example plan, three
  steps, six features). It ends with a privacy band whose wording matches the privacy page.
- **Setup wizard:** a numbered stepper with "Step N of 4". Each step is a card with its title,
  why it is asked, and the step's buttons in the footer: Back on the left, the way forward on the
  right. When the step changes, focus moves to the new step's title. Choices are selectable cards
  rather than bare radio buttons.
- **Plan:**
  - At the top, the summary: degree progress (ring, "60%" with "+12% in progress" in the
    in-progress colour), expected graduation, the longest prerequisite chain, and the GPA card
    (CGPA, last term, one retake suggestion with the rest behind "Other retake options").
  - Below it, tabs: Plan · Requirements · Degree map · Explore courses · Notes. The tab is kept in
    the address (`/plan#map`), and old links (`#next-term`, `#electives`) still open the right tab.
  - In the Plan tab, each course row stays compact. "Replace with" is always visible; "Keep in
    term" and the what-if open from the row's chevron. The next term is marked "Up next".
  - Plan settings sit behind "Adjust plan". While a change is applied, the plan stays on screen,
    dimmed, with a floating "Updating your plan…" notice instead of going blank.
- **Courses:** a large search field and a card grid. Results stay on screen while a new search
  runs.
- **Course page:** a header card, then the description and rules (each rule beside its SIS
  sentence) on the left, and "Opens" and "Counts toward" on the right.
- **Privacy:** a short list of plain commitments, each with an icon, and the clear-data action.

## Accessibility checklist for any change

- WCAG 2.1 AA, checked with axe in both light and dark mode, on every page and every plan tab.
- Keyboard: everything reachable, with a visible focus ring (3px maroon). Focus order follows
  the visual order.
- Targets: buttons are at least 36px tall, and main actions 44px.
- Phone: check at 375–390px. Tab bars scroll sideways inside themselves, never the page.
- Next 16 keeps recently visited pages mounted but hidden. E2E tests should find elements by
  role, or within a region, rather than by bare text, which may also match a hidden page.
