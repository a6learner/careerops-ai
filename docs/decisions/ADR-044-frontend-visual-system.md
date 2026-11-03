# ADR-044: Frontend Visual System And Page Structure

## Status

Accepted on 2026-10-29. The author approved the direction after reviewing
screenshots of a first violet design and then a Notion-inspired revision.

## Context

The MVP scope document limited the frontend to a demo layer and listed "design
system" and "animation system" as out of scope. P1-13 also said hardening should
happen "without a broad UI redesign". By 2026-10-28 the frontend worked but had
concrete problems:

- design tokens were mixed with raw Tailwind palette classes, and the Inter font
  was named in CSS but never loaded;
- base element styles sat outside a Tailwind layer, so `font: inherit` overrode
  every `text-sm` on buttons, inputs and selects;
- the sidebar had no active state, and Experiences and Projects shared one icon;
- each job card nested status, parsing and analysis, so evidence rows were
  cramped and there was no job detail page, although the MVP spec lists one;
- parse and analysis results disappeared on reload because run IDs lived only in
  component state;
- loading states were text-only, status was plain text in places, and project
  record withdrawal had no confirmation.

The author asked for a better-looking interface and chose a Notion-inspired
direction.

## Decision

Adopt a small, locally owned visual system. This supersedes only the "design
system" exclusion in the MVP frontend scope and the "without a broad UI
redesign" wording in P1-13. The other exclusions (animation system, drag and
drop, complex wizards, mobile-specific optimization) still apply.

- Tokens live once in `frontend/src/app/globals.css` and are registered with
  Tailwind v4 `@theme`: warm neutral text, white pages, a light sidebar, a blue
  action color and the Notion-style nine-color tag palette.
- Inter and JetBrains Mono load through `next/font/google`, which self-hosts them
  at build time; there is no runtime font CDN.
- Shared primitives in `frontend/src/components/ui/`: Button, Card, Input,
  Select, Textarea, Field, StatusBadge (tags), Skeleton, PageHeader,
  SectionHeading, Callout, EmptyState and a dependency-free Toast.
- Page structure: Jobs and Action Items are status boards, Experiences is a
  gallery, Projects is a page list with a document-style detail, and each job has
  a detail page at `/jobs/[id]` with properties, requirements, evidence and the
  description. Status changes use a menu on the card; there is no drag and drop.
- The workspace has route-level `loading`, `error` and `not-found` pages.
- No new npm dependency was added.

Styling copies a general design language only. The product does not use
Notion's name, logo or branding.

## Alternatives considered

- **Keep the original look and fix defects only.** This is lower risk, but it
  does not address the author's request and leaves the crowded job cards.
- **Adopt a component library (shadcn registry, Radix, MUI).** Rejected: ADR-037
  chose a small locally owned layer, and the project has no second consumer that
  would justify the dependency.
- **A dark violet "Linear-style" theme.** Built and screenshotted first. The
  author preferred the Notion-inspired direction.

## Consequences

- Visual rules have one home. New pages should reuse the primitives instead of
  adding raw palette classes.
- Component tests and the Playwright core loop changed with the markup: the
  jobs flow now opens the job detail page, and record withdrawal has a confirm
  step.
- Fonts need network access at image build time.
- The frontend weight in the project stays small. The backend and evidence
  guarantees are unchanged by this ADR; ADR-045 covers the API additions that
  the job detail and dashboard pages use.

## Verification or evidence

- `npm run lint`, `npm run typecheck`, `npm test` and `npm run build` pass.
- Preview screenshots with synthetic data:
  `docs/design/2026-10-28-redesign-preview/`.
- Full-stack browser acceptance results are recorded in
  `docs/metrics/2026-10-29-ui-polish-test-record.md`.
