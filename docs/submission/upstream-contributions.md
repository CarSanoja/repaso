# Upstream contributions: verified evidence

Verified against the public GitHub pages and GitHub API on September 14, 2026. Both pull requests were authored by **CarSanoja**, are **open**, and have **not been merged**. The canonical upstream repository currently resolves to `strands-agents/harness-sdk`.

| Contribution | Problem addressed | Evidence and status |
| --- | --- | --- |
| Model identity in telemetry | Custom model providers and wrappers could lose their model identifier in tracing when the SDK read an attribute outside the declared provider interface. The proposed fix uses the interface accessor, preserves a compatibility fallback, and adds regression coverage for agent, model and memory-extraction traces. | [PR #4207: telemetry model identification](https://github.com/strands-agents/harness-sdk/pull/4207), opened September 6; **open, not merged**. |
| Streaming interface contract | The event loop supplied model-state and cache-boundary arguments absent from the declared streaming interface. The proposed change documents those arguments in the interface and provider guide, with tests for contract drift. | [PR #4208: streaming interface arguments](https://github.com/strands-agents/harness-sdk/pull/4208), opened September 6, updated September 12; **open, not merged**. |

The author explains in the discussion on [PR #4207](https://github.com/strands-agents/harness-sdk/pull/4207) that the problem emerged while wrapping models for deterministic recording and replay in this hackathon project. This is evidence of the contribution's origin, not an upstream endorsement of Repaso.

## Wording for the README and presentation

“Building Repaso also led us to submit two upstream bug-fix pull requests to Strands Agents: one for trace attribution and one for the streaming provider contract. Both include regression tests and remain open for upstream review.”

Spanish: “Construir Repaso también nos llevó a proponer dos correcciones al proyecto Strands Agents: una para identificar el modelo en las trazas y otra para alinear la interfaz de streaming con lo que envía el runtime. Ambas incluyen pruebas de regresión y siguen abiertas.”

Use this as technical evidence after showing the working product. It supports genuine implementation effort and understanding of the SDK. It does not establish educational outcomes, production adoption, an AWS partnership, or acceptance of the fixes.

Do not describe these as merged fixes, fixes to AWS SDKs generally, or fixes already released by upstream. Test counts stated in the PR descriptions are the contributor's reported validation; this release audit verified the PR content and status, not a fresh execution of the upstream suites.

## Recheck before publication

```sh
gh pr view 4207 --repo strands-agents/harness-sdk --json author,state,isDraft,mergedAt,url
gh pr view 4208 --repo strands-agents/harness-sdk --json author,state,isDraft,mergedAt,url
```

The current deployed behavior of Repaso must be demonstrated independently; submitted upstream patches alone do not prove what is installed in its runtime.
