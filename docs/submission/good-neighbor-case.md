# Proposed case: community learning follow-up

Research and product recommendation, September 14, 2026. This is a proposed
Good Neighbor Agents direction, not a record of a partner, pilot, or completed
coordinator workflow. The existing submission copy still describes the family
product and must only change to match functionality actually demonstrated.

## Decision

Build the demonstration around a community learning facilitator helping a small
group practise foundational mathematics between meetings. Families use Telegram;
the facilitator sees evidence, pending decisions, and what happened after an
intervention. Begin with fourth-grade mathematics, supported printed material,
an adult contact, and internet access.

Proposed pitch: **Repaso keeps a community's learning support connected—from the
school page, through practice at home, to the next human intervention.**

The distinctive hypothesis is continuity of action: source → practice → observed
difficulty → human decision → changed practice → recorded follow-up. Memory is
useful because it changes an action and makes the reason inspectable. Do not
claim that memory or parent messaging is itself new.

## Documented foundation

1. **A concrete workflow in Zulia.** A UNICEF article published March 3, 2021,
   describes work in June 2020: each facilitator followed 25 children through
   home visits, WhatsApp or SMS where available, and community-centre activities.
   Learning guides included mathematical and logical thinking. This is a
   historical delivery model, not a verified current staffing ratio. Telegram
   is our implementation channel, not the channel used in that account.
   [UNICEF field account](https://www.unicef.org/venezuela/en/stories/education-cannot-wait-programme-doesnt-stop-during-quarantine).
2. **Recent need and an existing response.** UNICEF's end-2025 Venezuela report
   estimates 2.7 million children needing educational support and 1.5 million
   out of school. It records remedial programmes reaching 4,073 out-of-school
   children, with 1,511 participants reintegrated into formal schools; partners
   included Fe y Alegría and ASEINC. These are UNICEF programme figures, not
   Repaso outcomes, causal effects, or a measure of families reachable digitally.
   [UNICEF 2025 report, page 6](https://www.unicef.org/media/178481/file/Venezuela-Humanitarian-SitRep-No.2-(End-of-Year),-31-December-2025.pdf.pdf).
3. **Evidence for the communication mechanism.** Papás al Día studied roughly
   1,000 children in seven low-income Chilean schools. J-PAL reports a 0.09
   standard-deviation improvement in mathematics grades and a 2.7 percentage-point
   reduction in failing mathematics. The experiment concerned informational SMS,
   not AI tutoring, Telegram, or Repaso. It supports testing timely, actionable
   communication; its effects cannot be transferred to this product.
   [J-PAL evaluation](https://www.povertyactionlab.org/evaluation/reducing-parent-school-information-gaps-and-improving-education-outcomes-evidence-high).

No named organisation has commissioned, endorsed, tested, or partnered with
Repaso on the evidence available here. Use a fictional centre and synthetic
families, labelled explicitly. Do not reuse children's stories or images as
though they were product users.

## Alternatives considered

| Case | Strength | Main gap | Decision |
| --- | --- | --- | --- |
| Extra practice for families unable to afford tutoring | Clear access concern; close to existing family flow | No verified local affordability count or tutoring-equivalence result; collective workflow less visible | Supporting motivation |
| General school–parent messaging | Direct experimental precedent | Broad integration scope; messaging alone gives a weak originality argument | Mechanism, not whole product |
| Community catch-up group with persistent follow-up | Documented facilitator workflow; clear group benefit; memory has an observable consequence | Coordinator permissions and decision-return path need implementation | Selected case |

## Smallest convincing demonstration

Use three synthetic families in one authorised group. The historical group size
of 25 is context, not a claim that 25 live families or sessions were tested.

1. Show the learning objective and authorised printed material.
2. The user operates Telegram for one demonstration family. Its practice and
   answers update the same records displayed in the facilitator view.
3. Show a repeated competency difficulty across the synthetic group, including
   the observations and dates behind it. Clearly label prepared history.
4. A facilitator reviews a proposed intervention and confirms an action.
5. Show the actual resulting family message or changed next practice, its
   delivery status, and the persisted decision. Label any clock advance.

The facilitator view answers: Who needs attention? What evidence supports that?
What decision was made? Did the next action happen? Operational traces and costs
are secondary inspectable details, not the main experience.

## Build order and acceptance gates

1. Verify the current deployed family journey and correlate Telegram activity
   with persisted state. Deployment existence alone is insufficient.
2. Add a narrow coordinator view with explicit group membership and access
   boundaries, then expose existing learning evidence and cohort signals.
3. Implement one authorised coordinator decision through to a visible,
   recoverable family effect. This is new work: existing cohort notes are routed
   through a parent, and a full school–family coordinator loop is not implemented.
4. Record the working slice, correct submission claims, publish the required
   assets, and submit before the official deadline. Protect time for delivery;
   reduce scope if the group loop cannot be verified.

Missing replies mean **no response observed**, not dropout, disengagement, or
low mastery. Telegram acceptance is a delivery acknowledgement, not proof that
a family read the message. Do not imply offline operation or school replacement.

## Numbers to collect from our own demonstration

- Wall-clock time from Telegram input to persisted result and visible update.
- Human decisions required and whether each produces its intended effect.
- Practices scheduled, acknowledged by the transport, and completed, separately.
- Model calls and reported usage for this run; excluded costs stated explicitly.
- Correct isolation across groups and families, and no repeated learning effect
  on event replay.

Do not claim reduced dropout, learning gains, facilitator time savings, or a
cost advantage over private tuition without an appropriate measurement.
