# Diagram conventions

Inline SVG only; the template's CSS styles these classes in light and dark.

- One accent colour for the subject: put `class="accent"` on its boxes and edges; everything else stays neutral.
- Components are containers: `<rect class="box">` with a `<text class="label">`; nested parts sit inside.
- Edges: `<line class="edge" marker-end="url(#arrow)">`; an interface agents negotiated without a shared contract is
  dashed: `class="edge negotiated"`.
- Sequence diagrams: at most 8 participants and 15 messages; collapse the rest into one "…" message.
- Every diagram gets a one-line caption saying what to notice: `<figcaption>`.

## Block diagram

```html
<figure>
  <svg viewBox="0 0 640 220" role="img" aria-label="Orders and Billing each own a Customer model">
    <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" class="arrowhead"/></marker></defs>
    <rect class="box accent" x="20" y="40" width="180" height="120" rx="8"/>
    <text class="label" x="110" y="64" text-anchor="middle">orders</text>
    <rect class="box" x="440" y="40" width="180" height="120" rx="8"/>
    <text class="label" x="530" y="64" text-anchor="middle">billing</text>
    <line class="edge negotiated accent" x1="200" y1="100" x2="440" y2="100" marker-end="url(#arrow)"/>
    <text class="note" x="320" y="92" text-anchor="middle">customerAdapter</text>
  </svg>
  <figcaption>The adapter is the only thing keeping the two Customer models in step.</figcaption>
</figure>
```

## Sequence diagram

```html
<figure>
  <svg viewBox="0 0 640 240" role="img" aria-label="A retry goes through the queue worker">
    <text class="label" x="80" y="20" text-anchor="middle">billing</text>
    <text class="label" x="320" y="20" text-anchor="middle">queue</text>
    <text class="label" x="560" y="20" text-anchor="middle">worker</text>
    <line class="lifeline" x1="80" y1="30" x2="80" y2="230"/>
    <line class="lifeline" x1="320" y1="30" x2="320" y2="230"/>
    <line class="lifeline" x1="560" y1="30" x2="560" y2="230"/>
    <line class="msg" x1="80" y1="60" x2="320" y2="60" marker-end="url(#arrow)"/>
    <text class="note" x="200" y="54" text-anchor="middle">enqueue charge</text>
    <line class="msg accent" x1="320" y1="110" x2="560" y2="110" marker-end="url(#arrow)"/>
    <text class="note" x="440" y="104" text-anchor="middle">retry ×3</text>
  </svg>
  <figcaption>Retries happen in the worker, so a change in billing never sees them.</figcaption>
</figure>
```

Reuse the `arrow` marker from the first diagram, or define it again with another id in each `<svg>`.
