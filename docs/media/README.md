# Diagrams and product images

## Current architecture

[architecture.svg](architecture.svg) is the maintained source for the September 14, 2026 School Community Memory architecture. [architecture.png](architecture.png) is its rendered 1600 × 1200 export. Both describe the implemented transport, AgentCore runtime, four Strands graphs, application-owned learning memory and separate read-only observer.

The runtime's live Telegram evidence and the observer's local availability are deliberately separate. The diagram does not imply that every graph has completed a live school journey, that AgentCore Memory is provisioned, or that a stored review date guarantees delivery. See the [live record](../submission/memory-live-check-2026-09-14.md) and [judging guide](../submission/judging.md).

The SVG is code-native and editable without design software. The PNG was rendered in Chromium and visually checked for clipped labels, connections and legibility. Edit the SVG first, then regenerate and inspect the PNG at its native size before publishing.

## Verified product screenshots

- [Family dashboard](../submission/assets/family-dashboard-rehearsal.png): synthetic rehearsal with a controlled next-day clock.
- [Three-column episode](../submission/assets/episode-observer-rehearsal.png): synthetic rehearsal with two retained explanation approaches and zero assessed answers.

These are screenshots of the running product. They must retain their synthetic-rehearsal captions when used in documentation or a recording; they are not evidence of a school pilot.

## Historical figures

The other SVG/PNG files in this directory are historical August 2026 design and simulator artifacts. They are not current submission evidence. Some contain superseded agent counts, transport guarantees, unsupported modalities or model statistics. Do not use them in the final video without revising and verifying them against current code.

The current [README](../../README.md), [product implementation](../product/how-it-works.md) and [evidence register](../evidence/README.md) provide the supporting source links and boundaries.
