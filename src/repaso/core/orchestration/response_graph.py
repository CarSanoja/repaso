from collections import Counter
from datetime import date, timedelta

from strands.multiagent.graph import GraphBuilder

from repaso.agents.adaptation_policy import build_signals, decide
from repaso.agents.capsule_composer import item_buttons, render_item
from repaso.agents.escalation_composer import compose_engagement, compose_struggle
from repaso.agents.grader import grade_mcq, grade_open
from repaso.config.models import ModelRole
from repaso.core.harness.calendar import mask_to_scheduled
from repaso.core.harness.clock import local_date
from repaso.core.harness.escalation_triggers import DEFAULT_COOLDOWN_DAYS, DEFAULT_SILENT_DAYS
from repaso.core.orchestration.adaptations import apply_adaptation
from repaso.core.orchestration.answer_outcome import (
    EXPECTED_ANSWER_SECONDS,
    record_answer_outcome,
)
from repaso.core.orchestration.context import Services, TutorRun
from repaso.core.orchestration.nodes import StepNode
from repaso.core.orchestration.response_signals import (
    days_since_struggle,
    latency_window,
    struggle_evidence,
)
from repaso.i18n.catalog import msg
from repaso.schemas.channel import Button, OutboundMessage
from repaso.schemas.escalation import Escalation
from repaso.schemas.family import Family
from repaso.schemas.grading import GradeResult
from repaso.schemas.item import ItemKind
from repaso.schemas.review import QuarantineItem
from repaso.schemas.session import SessionStatus
from repaso.tools.episode_log import record_grade
from repaso.tools.grade_log import effective_grades

SIGNAL_WINDOW_DAYS = 14
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


def window_days(services: Services) -> list[date]:
    today = services.clock.today()
    return [today - timedelta(days=offset) for offset in range(SIGNAL_WINDOW_DAYS - 1, -1, -1)]


def daily_counts(services: Services, student_id: str) -> list[int]:
    per_day = Counter(
        local_date(g.responded_at or g.graded_at)
        for g in effective_grades(services.grade_log.by_student(student_id))
    )
    return [per_day.get(day, 0) for day in window_days(services)]


def scheduled_counts(services: Services, student_id: str, family: Family) -> list[int]:
    return mask_to_scheduled(
        window_days(services),
        daily_counts(services, student_id),
        family.rest_weekdays,
        services.settings.holiday_dates,
    )


def build_response_graph(services: Services, run: TutorRun):
    settings = services.settings

    async def grade() -> None:
        item = run.items[0]
        now = services.clock.now()
        cached = run.operation.payload.get("grade") if run.operation else None
        if cached:
            run.grade = GradeResult.model_validate(cached)
            if held := run.operation.payload.get("quarantine"):
                run.quarantine = QuarantineItem.model_validate(held)
        elif item.kind is ItemKind.MCQ:
            run.grade = grade_mcq(item, run.response, now)
        else:
            run.grade, run.quarantine = await grade_open(
                item,
                run.response,
                run.family.lang,
                services.model(ModelRole.JUDGE),
                settings.grader_confidence_threshold,
                now,
                run.family.id,
                llm_text=services.screener.redact(run.response.text),
            )
        run.grade.responded_at = run.response.received_at
        run.grade.id = f"answer:{run.session.id}:{run.session.current_item_index}"
        if run.operation:
            run.operation.payload["grade"] = run.grade.model_dump(mode="json")
            run.operation.payload["quarantine"] = (
                run.quarantine.model_dump(mode="json") if run.quarantine else None
            )
            services.store.put_record(run.operation)
        services.grade_log.append(run.grade)
        record_grade(
            services.store,
            run.family.id,
            run.session.id,
            item.competency_id,
            run.grade,
            run.response,
        )
        if run.quarantine is not None:
            run.quarantine.payload["grade_id"] = run.grade.id
            services.store.put_quarantine(run.quarantine)
            buttons = [
                Button(
                    label=msg("quarantine_approve", run.family.lang),
                    callback_data=f"quar:{run.quarantine.id}:yes",
                ),
                Button(
                    label=msg("quarantine_reject", run.family.lang),
                    callback_data=f"quar:{run.quarantine.id}:no",
                ),
                Button(
                    label=msg("quarantine_unsure", run.family.lang),
                    callback_data=f"quar:{run.quarantine.id}:later",
                ),
            ]
            prompt = msg(
                "quarantine_prompt",
                run.family.lang,
                alias=run.student.alias,
                answer=run.response.text,
            )
            prompt += (
                f"\n\n{item.stem}\n\n"
                + ("Respuesta esperada" if run.family.lang.value == "es" else "Expected answer")
                + f": {item.answer_key}\n"
                + (item.rubric or item.rationale)
            )
            _say(run, prompt, buttons)

    async def apply() -> None:
        item = run.items[0]
        if run.grade.correct is not None:
            record_answer_outcome(
                services,
                run.student.id,
                item,
                run.grade.correct,
                run.response.latency_seconds,
                outcome_id=f"answer:{run.session.id}:{run.session.current_item_index}",
            )
            if run.grade.correct:
                said = msg("feedback_correct", run.family.lang, feedback=run.grade.feedback)
                _say(run, said.strip())
            else:
                reason = run.grade.feedback or item.rationale
                _say(run, msg("feedback_incorrect", run.family.lang, feedback=reason).strip())
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
            closing = "session_complete" if streak else "session_complete_fresh"
            _say(run, msg(closing, run.family.lang, streak=streak))
        services.store.put_session(run.session)

    async def adapt() -> None:
        item = run.items[0]
        mastery = services.store.get_mastery(run.student.id, item.competency_id)
        if mastery is None:
            run.decision_action = "continue"
            return
        signals = build_signals(
            mastery,
            daily_counts(services, run.student.id),
            latency_window(services, run.student.id, run.response.latency_seconds),
            EXPECTED_ANSWER_SECONDS,
            settings.escalation_min_samples,
            days_since_struggle(services, run.family.id, run.student.id),
            DEFAULT_COOLDOWN_DAYS,
        )
        cached = run.operation.payload.get("decision") if run.operation else None
        run.decision_action = (
            cached or (await decide(signals, services.model(ModelRole.STRUCTURED))).action
        )
        if run.operation:
            run.operation.payload["decision"] = run.decision_action
            services.store.put_record(run.operation)
        apply_adaptation(
            services,
            run.family,
            run.student.id,
            item.competency_id,
            run.decision_action,
            item.difficulty,
            source=f"answer:{run.session.id}:{run.session.current_item_index}",
        )
        services.telemetry.trace(
            "decision",
            run.decision_action,
            student_id=run.student.id,
            family_id=run.family.id,
            competency=item.competency_id,
        )

    async def escalate() -> None:
        item = run.items[0]
        competency = services.retriever.get_competency(item.competency_id)
        cached = run.operation.payload.get("escalation") if run.operation else None
        if cached:
            escalation = Escalation.model_validate(cached)
        elif run.decision_action == "escalate_struggle":
            escalation = await compose_struggle(
                run.family.id,
                run.student.id,
                run.student.alias,
                competency,
                struggle_evidence(services, run.student.id, item.competency_id, run.grade.evidence),
                run.family.lang,
                services.model(ModelRole.GENERATE),
                services.clock.now(),
            )
        else:
            escalation = compose_engagement(
                run.family.id,
                run.student.id,
                run.student.alias,
                DEFAULT_SILENT_DAYS,
                run.family.lang,
                services.clock.now(),
            )
        if run.operation:
            run.operation.payload["escalation"] = escalation.model_dump(mode="json")
            services.store.put_record(run.operation)
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
