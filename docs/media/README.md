# Diagram system

Every diagram in this directory is **hand-authored SVG**, rendered to PNG for
publication and visually inspected before it ships. This file documents the method so
the next diagram looks like it belongs to the same family.

## Why hand-written SVG

Not Mermaid, draw.io, Excalidraw or a screenshot of a whiteboard.

| Reason | Consequence |
|---|---|
| Total compositional control | A governance plane drawn *inside* the runtime box, a legend aligned to a specific edge, a measured number placed exactly under the stage that produced it — layout choices a graph-layout engine will not make |
| Real, selectable text | Searchable, translatable, readable by screen readers rather than baked into pixels |
| Diffable in git | A one-line change to a label is a one-line diff, not a new binary blob |
| Zero dependencies | Anyone with a text editor can edit it; no account, no tool, no export step |
| Deterministic | The same source always produces the same image — no auto-layout drift between renders |

The cost is that nothing catches a mistake for you. That is what the loop below is for.

## The loop that actually makes it work

Writing SVG blind produces overlapping text and misaligned arrows. The method is
**write → render → look → fix**, and the looking is not optional:

```bash
# 1. author or edit the SVG
# 2. render it to PNG (macOS Quick Look, no install needed)
qlmanage -t -s 2400 -o docs/media docs/media/<name>.svg
mv docs/media/<name>.svg.png docs/media/<name>.png
# 3. OPEN THE PNG AND LOOK AT IT — every pass, without exception
# 4. fix what the eye caught, re-render, look again
```

Render at `-s 2400` for anything going into a submission gallery: presentation
surfaces resample images and thin strokes disappear at small sizes.

## Visual system

Colours follow the AWS/Cloudscape palette, so the diagram reads as native to the
platform it runs on.

| Token | Hex | Meaning — used for nothing else |
|---|---|---|
| AWS orange | `#ff9900` | AWS-managed services we consume (Bedrock, AgentCore, Textract, Polly) |
| Orange wash | `#fff4e5` | Background of an AWS-managed region |
| Blue | `#0972d3` | Our own code and compute (graphs, agents, Lambda handlers, the API) |
| Blue wash | `#eaf3fd` | Background of an "ours" region |
| Green | `#037f0c` | Deterministic harness and state — the auditable, non-LLM half |
| Green wash | `#eaf6ea` | Background of a harness/state region |
| Red | `#d91515` | Governance, refusal, containment — anything that *stops* something |
| Red wash | `#fdeceb` | Background of a governance region |
| Purple | `#6b40b2` | Human-facing surfaces, where a person appears |
| Purple wash | `#f2ecfa` | Background of a human region |
| Squid ink | `#232f3e` | Transport and infrastructure spine (EventBridge, SQS, API Gateway) |
| Grey | `#5f6b7a` / `#8c99a8` | Arrows, captions, secondary text |
| Ink | `#0f1b2a` / `#3c4650` | Primary text |

Type: Helvetica/Arial stack throughout. Title 27px bold, subtitle 14px, box titles
14–16px bold, body 11.5–12.5px, captions 10.5–11px italic. Never below 10.5px — these
are read on a projector and inside a video.

Shape grammar, applied consistently so shape carries meaning:

- **Rounded rect (`rx=10-12`)** — a system, service or region
- **Sharp rect (`rx=7`)** — a graph node; nodes sit in a row in execution order
- **Solid arrow** — data or control flow, direction is literal
- **Double-headed arrow** — a read/write relationship
- **Dashed grey line** — a temporal or logical link, not a data path ("the same family, next morning")
- **Dotted vertical leader** — ties an annotation to the thing it annotates when they cannot touch
- **Red octagon or bar** — a gate that can refuse; it never sits on the happy path without a visible exit

## Rules learned the hard way

1. **Annotations under a row of boxes must alternate rows.** Two lines of text under
   adjacent 76px-wide boxes will collide. Stagger them and add leaders.
2. **Give every region an explicit background.** A transparent region inherits whatever
   is behind it and the grouping stops reading.
3. **One idea per diagram.** If a box needs a paragraph, that paragraph is a different
   diagram.
4. **Label the arrows that are not obvious.** `claim (exactly-once)`, `redacted text`,
   `k ≥ 3 families` are facts; an unlabelled arrow is a guess.
5. **Put the numbers in.** Measured precision, latency and counts turn an architecture
   drawing into evidence. **Only real measurements** — every number must trace to a
   dated benchmark run. Never a number you have not seen come out of a run.
6. **Design for both light and dark presentation.** The background is painted explicitly
   white; text is dark ink. Never rely on the host's background.
7. **The deterministic half must look different from the model half.** Green for the
   harness, blue for our agents, orange for Bedrock: a reader should be able to see, at
   a glance, that the pedagogy is not a model's opinion.

## Files

Each diagram ships as a pair: `<name>.svg` (source of truth, edit this) and
`<name>.png` (2400px render for submissions and slides).

| Diagram | Level | Shows | Read it if you are |
|---|---|---|---|
| [`architecture`](architecture.svg) | overview | The whole system on one page: the three graphs, the 13 agents, the deterministic harness, memory tiers and the AWS plane | Anyone — this is the front door |
| [`context`](context.svg) | 1 — context | The family and school world around the agent: who touches it, who never does, and what crosses the boundary | Non-technical: a judge, a school, leadership |
| [`containers`](containers.svg) | 2 — containers | Deployable units on AWS, the data each owns, and the identity carried on each hop | An engineer deciding whether this is real |
| [`graphs`](graphs.svg) | 3 — graphs | The four Strands graphs node by node: conditional edges, stage claims, and where each one refuses | Anyone reviewing the orchestration |
| [`fleet`](fleet.svg) | 3 — agents | The 13 agents with their model, graph, deterministic counterpart and blast radius | Anyone auditing the "agent fleet" claim |
| [`interruption-contract`](interruption-contract.svg) | 3 — controls | Every gate a message must pass before it may interrupt a human, in the order they apply, with what each one stopped | Anyone asking "will this spam a parent?" |
| [`child-safety`](child-safety.svg) | 3 — controls | The parent-gateway model, the Armor, PII redaction and the data a child never has | Anyone responsible for minors' data |
| [`cohort-signal`](cohort-signal.svg) | 3 — feature | The hero innovation: k-anonymous section aggregation into a drafted teacher note, and what it refuses to reveal | Anyone evaluating novelty |
| [`family-journey`](family-journey.svg) | people | The parent's real screens across a first week, and the two moments they are asked to decide | Product, design, pilot families |
| [`evidence`](evidence.svg) | method | How a claim becomes credible here: pre-registered gates, seed hygiene, held-out validation, and a falsified proposal | Anyone asking "why should I believe these numbers?" |
| [`resilience`](resilience.svg) | flow | The failure modes actually executed — crash-resume, duplicate delivery, outage silence, model throttle — and how each recovers | Anyone who has run production systems |
| [`self-learning`](self-learning.svg) | roadmap | The learning loops and their adversaries: what updates, who challenges it, and the gate that promotes a change | Anyone assessing the learning claim |

Every number in these diagrams comes from a dated benchmark run. Where a
control is designed but not yet proven live, the diagram says so on its face rather than
implying more than was measured.
