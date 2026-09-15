# Release record - September 14, 2026

The product release is public and merged. The final video and Devpost submission
remain separate delivery steps. This record distinguishes published source,
verified execution and submission items that still need a public link or receipt.

## Public source and release validation

| Item | Verified state |
| --- | --- |
| Public repository | [CarSanoja/repaso](https://github.com/CarSanoja/repaso), public, with MIT license |
| Product release | [PR #8](https://github.com/CarSanoja/repaso/pull/8) merged September 14 at 23:25:06 UTC |
| Released commit | [`e04f7ff6d5cdc088b7c707a51fd006e9e5dd6fb6`](https://github.com/CarSanoja/repaso/commit/e04f7ff6d5cdc088b7c707a51fd006e9e5dd6fb6); GitHub reports a valid verified signature |
| Security follow-up | [PR #9](https://github.com/CarSanoja/repaso/pull/9), commit [`119e8ca`](https://github.com/CarSanoja/repaso/commit/119e8ca39f2ed0d9ac01fb412a6f9bf7c4562ce2), merged at 23:34:42 UTC; constant asset paths and diagnostic-only hygiene output |
| Local release suite | **2,134 passed, 66 skipped** |
| Latest CI application suite | **2,011 passed, 93 skipped** after the security follow-up; environment-dependent skips are reported separately from local validation |
| CI infrastructure suite | **128 passed** |
| CI quality and security checks | Lint, hygiene, infrastructure, tests, analysis and CodeQL passed; [latest CI run](https://github.com/CarSanoja/repaso/actions/runs/34909231486) |
| Installed distribution | Wheel built and installed; the two installed-package journeys passed **24/24** and **23/23** checks |
| Dependency correction | Build dependency updated to `setuptools` 83 |
| GitHub alerts | **0 open Dependabot, 0 open CodeQL/code-scanning and 0 open secret-scanning alerts**, checked after the default-branch analysis of `119e8ca`; both CodeQL findings automatically marked fixed at 23:35:41 UTC |
| Documentation | README, MIT license, declared dependencies, architecture diagram, deployment guidance and judge instructions are present |

The product commit above is the release reference, not a claim that the Devpost
form has been submitted. Article, cover and final submission-document updates can
follow in a separate pull request.

The first default-branch CodeQL analysis found two issues in existing judge
tooling. PR #9 addressed both without dismissing or suppressing alerts. The
subsequent default-branch analysis reported zero findings. Alert counts describe
the observed scan state; they are not a guarantee that every possible flaw has
been eliminated.

## Main branch controls

Changes to `main` require a pull request. The required approval count is **zero**
for the solo-maintainer workflow; this does not mean an independent approval was
received. Required status checks are `lint`, `test`, `infra`, `hygiene`, `analyze`
and `CodeQL`, with strict up-to-date checking.

Protection also applies to administrators. Verified signatures, linear history
and resolved review conversations are required. Force pushes and branch deletion
are disabled. Merged feature branches are deleted automatically.

## Working product and retained evidence

| Item | Verified state and evidence |
| --- | --- |
| Deployed runtime | Amazon Bedrock AgentCore version 13 deployed; [live verification record](memory-live-check-2026-09-14.md) |
| Real Telegram interaction | Two successful requests for explanations produced different retained approaches. The second retrieved the previous approach; AWS memory and delivery records were linked to the replies. |
| Learning evidence boundary | The assessed count remained at three during those help requests. The earlier assessments repeated the same content; one day of activity does not establish learning improvement. |
| School Community Memory interface | Family/learner/topic/day filters, daily and cumulative evidence, stored review dates and human decisions; linked conversation, memory and topic evidence; explicit Replay mode |
| Browser verification | Dashboard and episode flows checked at desktop, divided-screen and mobile widths; source failure/recovery and retained-state rereads tested |
| Adult decision follow-through | Separate local rehearsal verifies that reducing practice changes the next scheduled capsule. Its family, model responses, transport and clock are explicitly synthetic. |
| Test build | [Judge instructions](judging.md) and [episode recording runbook](episode-demo-runbook.md); the loopback AWS observer is not a public hosted testing URL |
| Educational impact | No family pilot, independently reviewed learning gain or measured staff time saving is claimed; [evaluation kit](../../evaluation/README.md) and [pilot protocol](../pilot/README.md) remain available for that next work |

Earlier evidence remains useful with its original dates and conditions:
[Textract check](../evidence/live-ocr.json),
[September 12 model conformance](../evidence/live-conformance-2026-09-12.json),
[container smoke checks](../evidence/container-smoke.json), and the
[evidence register](../evidence/README.md). Historical test totals and synthetic
scenarios are not substituted for the release checks above.

## Submission handoff

| Item | Current state |
| --- | --- |
| Primary category | **Good Neighbor Agents - School Community Memory**; the community facilitator use case is proposed, while the demonstrated access model remains family scoped |
| Public code URL | Ready: [github.com/CarSanoja/repaso](https://github.com/CarSanoja/repaso) |
| README and architecture | Ready in the public repository; [architecture diagram](../media/architecture.svg) |
| Video narration | Ready: [annotated recording script](video-script.txt), [narration only for ElevenLabs](video-narration.txt), and [formatted script with sources](video-script.md); 317 spoken words, target 2:40, maximum 3:00 |
| Final video | The owner is generating it. **Public YouTube/Vimeo URL pending.** For the owner-reported three-minute judging window, confirm the complete export is no longer than 3:00, including titles and outro. Target 2:40; align captions to the final English audio and recorded evidence. |
| Builder Center article | **Published:** [Agents for Humans: School Community Memory with Repaso](https://builder.aws.com/content/3JL6ZEQTNgN6UIDQBfmjuHqjxoN/agents-for-humans-school-community-memory-with-repaso). [Article source](builder-post.md) retains its architecture link and literal hashtags. |
| Judge testing access | Supply the verified test-build instructions or an available project-access path in the form. Do not present `127.0.0.1` as a remotely accessible service. |
| AWS Builder ID and eligibility | Owner supplies the Builder ID email privately and confirms eligibility and [provenance](provenance.md) |
| Devpost form and receipt | **No completed submission is recorded.** Complete the form, attach the public source/video and testing instructions, then retain the submitted URL, receipt and final source reference. |
| Availability during judging | Maintain the testing path supplied in the form through the required judging period, including October 8. |

## Requirements audit

The [official rules](https://agentsforhumans.devpost.com/rules) specify the
September 14 deadline at **17:00 PDT / 20:00 Caracas**. Required materials include
a public MIT- or Apache-licensed code repository, README, architecture diagram,
project description, public YouTube/Vimeo demonstration video of at most five
minutes, AWS Builder ID and usable project access or test-build instructions.
The owner subsequently reported a 30-minute extension and that judges will watch
only three minutes. The revised recording therefore targets 2:40 with a strict
3:00 export maximum; this does not assert that the published rules were amended.
Submission materials must be English or accompanied by English translations.
A live demonstration link and AgentCore deployment strengthen the presentation
but are not mandatory submission requirements.

The rules update dated August 12 removed the literal `#AgentsforHumans` hashtag
requirement for eligible Builder Center articles. The prepared article title
contains **Agents for Humans**; its tags and hashtags remain useful publication
metadata. Builder Center articles are optional bonus material, not evidence that
the Devpost entry has been submitted.

Before clicking Submit, open the final public links while signed out, check the
video duration and testing instructions, and confirm the form describes the
released implementation. Retain the exact submitted materials and receipt.

Official references: [challenge overview](https://agentsforhumans.devpost.com/),
[rules](https://agentsforhumans.devpost.com/rules), and
[FAQ](https://agentsforhumans.devpost.com/details/faqs).
