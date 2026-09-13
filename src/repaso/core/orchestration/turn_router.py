from uuid import uuid4

from repaso.agents.grader import normalize
from repaso.agents.turn_reader import read_turn
from repaso.config.models import ModelRole
from repaso.core.orchestration import turn_memory
from repaso.core.orchestration.context import ChannelRun, Route, Services
from repaso.core.orchestration.ingest_holds import QUOTE_LENGTH, held_kind, offered_reply
from repaso.core.orchestration.runner import active_session, current_item, handle_answer
from repaso.core.orchestration.turn_replies import reply_to, say, speak
from repaso.core.orchestration.turn_target import (
    answering_student,
    build_target,
    focus_student,
    latency,
    turn_context,
)
from repaso.schemas.family import Family
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.item import Item, ItemKind
from repaso.schemas.review import QuarantineItem
from repaso.schemas.session import SessionStatus
from repaso.schemas.turn import PracticeState, TurnDecision, TurnIntent
from repaso.tools.guardrails import ScreenVerdict

READ_ROLE = ModelRole.STRUCTURED


async def route_turn(services: Services, run: ChannelRun, family: Family, text: str) -> None:
    verdict = services.screener.screen(text)
    if not verdict.safe:
        hold_blocked(services, run, family, verdict, text)
        return
    said = services.screener.redact(text)
    target = build_target(services, family, run.message.message_ref)
    run.student = target.student
    decision = await read_turn(
        said, turn_context(services, family, target), services.model(READ_ROLE)
    )
    if decision is None:
        run.route = Route.CONVERSATION
        speak(run, family, "turn_not_understood")
        return
    services.telemetry.trace(
        "turn",
        decision.intent.value,
        family_id=family.id,
        student_id=target.student.id if target.student else None,
    )
    if decision.intent is TurnIntent.ANSWER and target.state is PracticeState.OPEN:
        chosen = answer_for(target.item, decision, text, said)
        await route_answer(services, run, family, chosen)
        return
    await reply_to(services, run, family, target, decision, said)


async def route_answer(services: Services, run: ChannelRun, family: Family, text: str) -> None:
    student = answering_student(services, family)
    if student is None:
        run.route = Route.IGNORED
        return
    run.student = student
    run.route = Route.ANSWER
    session = active_session(services, student.id)
    item = current_item(services, session)
    index = session.current_item_index
    run.tutor = await handle_answer(
        services,
        family,
        student,
        text,
        latency(services, student.id, run.message.received_at),
        response_id=f"chat:{run.message.message_ref}",
    )
    remember_answer(services, run, family, item, index, text)


def remember_answer(
    services: Services,
    run: ChannelRun,
    family: Family,
    item: Item | None,
    index: int,
    text: str,
) -> None:
    tutor = run.tutor
    if tutor is None or tutor.session is None:
        return
    if tutor.grade is not None:
        turn_memory.remember(
            services,
            family.id,
            tutor.session.id,
            turn_memory.note(
                turn_id=run.message.message_ref,
                intent=TurnIntent.ANSWER,
                at=services.clock.now(),
                item=item,
                item_index=index,
                said=services.screener.redact(text),
                correct=tutor.grade.correct,
            ),
        )
    if tutor.session.status is SessionStatus.COMPLETED:
        turn_memory.close_window(services, family.id, tutor.session.id)


def names_an_option(item: Item, candidate: str) -> bool:
    options = [normalize(option) for option in item.options]
    chosen = normalize(candidate)
    if chosen in options:
        return True
    return chosen.isdigit() and 1 <= int(chosen) <= len(options)


def copied_verbatim(said: str, candidate: str) -> bool:
    return normalize(candidate) in normalize(said)


def answer_for(item: Item | None, decision: TurnDecision, text: str, said: str) -> str:
    candidate = decision.answer_text.strip()
    if not candidate or item is None or item.kind is not ItemKind.MCQ:
        return text
    if not copied_verbatim(said, candidate):
        return text
    return candidate if names_an_option(item, candidate) else text


def hold_blocked(
    services: Services, run: ChannelRun, family: Family, verdict: ScreenVerdict, text: str
) -> None:
    run.route = Route.CONVERSATION
    student = focus_student(services, family)
    services.store.put_quarantine(
        QuarantineItem(
            id=uuid4().hex,
            kind=held_kind(verdict),
            family_id=family.id,
            evidence=EvidenceSpan(
                quote=services.screener.redact(text)[:QUOTE_LENGTH],
                source_ref=f"chat:{student.id if student else family.chat_ref}",
            ),
            payload={"reasons": verdict.reasons, "student_id": student.id if student else ""},
            created_at=services.clock.now(),
        )
    )
    offered = offered_reply(verdict)
    if offered:
        say(run, family, offered)
        return
    speak(run, family, "turn_blocked")
