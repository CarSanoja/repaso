from collections import Counter
from datetime import timedelta

from strands.multiagent.graph import GraphBuilder

from repaso.agents.adaptation_policy import build_signals, decide
from repaso.agents.capsule_composer import item_buttons, render_item
from repaso.agents.escalation_composer import compose_engagement, compose_struggle
from repaso.agents.grader import grade_mcq, grade_open
from repaso.config.models import ModelRole
from repaso.core.harness.escalation_triggers import DEFAULT_COOLDOWN_DAYS, DEFAULT_SILENT_DAYS
from repaso.core.harness.mastery import update_mastery
from repaso.core.harness.sm2 import grade_to_quality, review
from repaso.core.orchestration.context import Services, TutorRun
from repaso.core.orchestration.nodes import StepNode
from repaso.i18n.catalog import msg
from repaso.schemas.channel import Button, OutboundMessage
from repaso.schemas.escalation import EscalationKind, EscalationStatus
from repaso.schemas.item import ItemKind
from repaso.schemas.mastery import MasteryState
from repaso.schemas.schedule import SpacedItemState
from repaso.schemas.session import SessionStatus

EXPECTED_ANSWER_SECONDS = 45.0
SIGNAL_WINDOW_DAYS = 14
LATENCY_WINDOW = 20
ESCALATION_ACTIONS = {"escalate_struggle", "escalate_engagement"}


def _say(run: TutorRun, text: str, buttons: list[Button] | None = None) -> None:
    run.outbound.append(
        OutboundMessage(
            channel=run.family.channel,
            chat_ref=run.family.chat_ref,
            text=text,
            buttons=buttons or [],
        )
    )


def daily_counts(services: Services, student_id: str) -> list[int]:
    today = services.clock.today()
    per_day = Counter(g.graded_at.date() for g in services.grade_log.by_student(student_id))
    days = [today - timedelta(days=offset) for offset in range(SIGNAL_WINDOW_DAYS - 1, -1, -1)]
    return [per_day.get(day, 0) for day in days]


def build_response_graph(services: Services, run: TutorRun):
    settings = services.settings

    async def grade() -> None:
        item = run.items[0]
        now = services.clock.now()
        if item.kind is ItemKind.MCQ:
            run.grade = grade_mcq(item, run.response, now)
        else:
            run.grade, run.quarantine = await grade_open(
                item, run.response, run.family.lang, services.model(ModelRole.JUDGE),
                settings.grader_confidence_threshold, now, run.family.id,
                llm_text=services.screener.redact(run.response.text),
            )
        services.grade_log.append(run.grade)
        if run.quarantine is not None:
            services.store.put_quarantine(run.quarantine)
            buttons = [
                Button(label=msg("quarantine_approve", run.family.lang),
                       callback_data=f"quar:{run.quarantine.id}:yes"),
                Button(label=msg("quarantine_reject", run.family.lang),
                       callback_data=f"quar:{run.quarantine.id}:no"),
            ]
            prompt = msg("quarantine_prompt", run.family.lang,
                         alias=run.student.alias, answer=run.response.text)
            _say(run, prompt, buttons)

    async def apply() -> None:
        item = run.items[0]
        if run.grade.correct is not None:
            mastery = services.store.get_mastery(run.student.id, item.competency_id)
            if mastery is None:
                mastery = MasteryState(
                    student_id=run.student.id, competency_id=item.competency_id,
                    ema_accuracy=0.0, attempts=0, correct=0,
                )
            services.store.put_mastery(
                update_mastery(mastery, run.grade.correct, services.clock.now())
            )
            spaced = {s.item_id: s for s in services.store.list_spaced(run.student.id)}
            state = spaced.get(item.id) or SpacedItemState(
                student_id=run.student.id, item_id=item.id, due_date=services.clock.today()
            )
            quality = grade_to_quality(
                run.grade.correct, run.response.latency_seconds, EXPECTED_ANSWER_SECONDS
            )
            services.store.put_spaced(review(state, quality, services.clock.today()))
            key = "feedback_correct" if run.grade.correct else "feedback_incorrect"
            _say(run, msg(key, run.family.lang, feedback=run.grade.feedback).strip())
        next_index = run.session.current_item_index + 1
        remaining = run.session.capsule.item_ids[next_index:] if run.session.capsule else []
        if remaining:
            run.session = run.session.model_copy(
                update={"current_item_index": next_index, "status": SessionStatus.IN_PROGRESS}
            )
            next_item = services.store.get_item(remaining[0])
            _say(run, render_item(next_item), item_buttons(run.session.id, next_item))
        else:
            run.session = run.session.model_copy(
                update={"status": SessionStatus.COMPLETED, "completed_at": services.clock.now()}
            )
            mastery = services.store.get_mastery(run.student.id, item.competency_id)
            streak = max(mastery.streak, 0) if mastery else 0
            _say(run, msg("session_complete", run.family.lang, streak=streak))
        services.store.put_session(run.session)

    def _latency_window(student_id: str) -> list[float]:
        grades = services.grade_log.by_student(student_id)
        window = [g.latency_seconds for g in grades if g.latency_seconds is not None]
        return window[-LATENCY_WINDOW:] + [run.response.latency_seconds]

    def _days_since_struggle(student_id: str) -> int | None:
        history = [
            e
            for e in services.store.list_escalations(run.family.id)
            if e.kind is EscalationKind.STRUGGLE_TRIAGE and e.student_id == student_id
        ]
        if not history:
            return None
        if any(e.status is EscalationStatus.PENDING for e in history):
            return 0
        latest = max(e.created_at for e in history)
        return (services.clock.today() - latest.date()).days

    async def adapt() -> None:
        item = run.items[0]
        mastery = services.store.get_mastery(run.student.id, item.competency_id)
        if mastery is None:
            run.decision_action = "continue"
            return
        signals = build_signals(
            mastery, daily_counts(services, run.student.id),
            _latency_window(run.student.id), EXPECTED_ANSWER_SECONDS,
            settings.escalation_min_samples,
            _days_since_struggle(run.student.id), DEFAULT_COOLDOWN_DAYS,
        )
        decision = await decide(signals, services.model(ModelRole.STRUCTURED))
        run.decision_action = decision.action
        services.telemetry.trace(
            "decision", decision.action, student_id=run.student.id,
            family_id=run.family.id, competency=item.competency_id,
        )

    def _struggle_evidence(student_id: str, competency_id: str) -> list:
        spans = []
        for grade in reversed(services.grade_log.by_student(student_id)):
            if grade.correct is False:
                item = services.store.get_item(grade.item_id)
                if item is not None and item.competency_id == competency_id:
                    spans.append(grade.evidence)
            if len(spans) == 3:
                break
        return list(reversed(spans)) or [run.grade.evidence]

    async def escalate() -> None:
        item = run.items[0]
        competency = services.retriever.get_competency(item.competency_id)
        if run.decision_action == "escalate_struggle":
            escalation = await compose_struggle(
                run.family.id, run.student.id, run.student.alias, competency,
                _struggle_evidence(run.student.id, item.competency_id), run.family.lang,
                services.model(ModelRole.GENERATE), services.clock.now(),
            )
        else:
            escalation = compose_engagement(
                run.family.id, run.student.id, run.student.alias,
                DEFAULT_SILENT_DAYS, run.family.lang, services.clock.now(),
            )
        services.store.put_escalation(escalation)
        run.escalations.append(escalation)
        buttons = [
            Button(label=option.label, callback_data=f"esc:{escalation.id}:{option.key}")
            for option in escalation.options
        ]
        _say(run, escalation.summary, buttons)

    def alive(_state) -> bool:
        return run.terminal is None

    def should_escalate(_state) -> bool:
        return run.decision_action in ESCALATION_ACTIONS

    builder = GraphBuilder()
    builder.add_node(StepNode("grade", grade, services.telemetry, "response"), "grade")
    builder.add_node(StepNode("apply", apply, services.telemetry, "response"), "apply")
    builder.add_node(StepNode("adapt", adapt, services.telemetry, "response"), "adapt")
    builder.add_node(StepNode("escalate", escalate, services.telemetry, "response"), "escalate")
    builder.add_edge("grade", "apply", condition=alive)
    builder.add_edge("apply", "adapt", condition=alive)
    builder.add_edge("adapt", "escalate", condition=should_escalate)
    builder.set_entry_point("grade")
    builder.set_max_node_executions(6)
    return builder.build()
