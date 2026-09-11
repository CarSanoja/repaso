"""Render a captioned reconstruction from synthetic run evidence, never a fake screen recording."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCENES = [
    (
        "A school page becomes a routine",
        "Repaso / Everyday Agents",
        0,
        "The parent already has school material. Repaso is designed to turn it into a"
        " short daily practice, then follow what happens next.",
    ),
    (
        "An agreed time. A parent in control.",
        "Enrollment and scheduling",
        0,
        "The family uses an alias and chooses a daily time. Enrollment creates a "
        "timezone-aware alarm. Pause, resume and schedule changes update that "
        "routine.",
    ),
    (
        "A reviewed practice bank",
        "Material to usable questions",
        0,
        "In this recorded case, five questions survive review. They belong to this "
        "family. A correct guess by the options-only probe cannot veto a valid "
        "exercise.",
    ),
    (
        "Practice arrives",
        "Simulated day 1 / 19:00 Caracas",
        1,
        "A short reminder arrives with a recognition question and reasoning practice."
        " The session becomes delivered only after the transport acknowledges the "
        "message.",
    ),
    (
        "A mistake becomes useful evidence",
        "Feedback with a counterexample",
        2,
        "The child says that adding the same number to the top and bottom keeps a "
        "fraction equal. The response explains why that rule changes the value.",
    ),
    (
        "Uncertainty reaches a person",
        "Question, answer, key and rubric",
        2,
        "An ambiguous explanation is held for the parent. The parent can mark it "
        "correct, incorrect, or say they do not know yet. Waiting is not approval.",
    ),
    (
        "One answer. One final outcome.",
        "Human review is preserved",
        3,
        "The parent approves this synthetic example. A final human assessment "
        "supersedes the provisional grade. A rejected answer also becomes a final "
        "outcome.",
    ),
    (
        "Bad material does not become practice",
        "A second, flawed worked example",
        4,
        "The additional guide claims that two thirds equals four ninths. Its "
        "generated exercises are rejected. The family is asked for a better source "
        "page.",
    ),
    (
        "A pattern needs attention",
        "SIMULATED TIME JUMP / two more school days",
        4,
        "After nine reviewed answers, persistent difficulty reaches the configured "
        "threshold. The parent receives evidence and two choices with concrete "
        "consequences.",
    ),
    (
        "A note the parent can use",
        "Choice A / parent decides whether to forward",
        5,
        "Choosing the teacher note delivers the actual draft to the parent. Repaso "
        "does not contact the teacher automatically. The next routine continues.",
    ),
    (
        "Or make the next week lighter",
        "Choice B / one exercise for seven days",
        6,
        "The alternative choice saves a seven-day workload reduction. The next "
        "practice contains one exercise instead of three. The choice changes the "
        "plan.",
    ),
    (
        "Four Strands graphs. Durable effects.",
        "Implemented production route / deployment pending",
        6,
        "The worker invokes AgentCore through SSM. DynamoDB transactions protect "
        "learning updates; journals and delivery receipts support recovery. Lost "
        "Telegram acknowledgments can still duplicate messages.",
    ),
    (
        "Evidence has different meanings",
        "Simulation / actual OCR / unmeasured outcomes",
        6,
        "Ten full adapter simulations passed with injected failures. A real "
        "Textract call read a new printed page, and every configured model answered "
        "its schema. None of it proves model quality or family benefit.",
    ),
    (
        "Try the whole story. Inspect the evidence.",
        "Local judge experience / both decisions",
        6,
        "The candidate covers fourth-grade math and printed material. Deployed "
        "acceptance, teacher review and a family pilot remain open. This preview "
        "reconstructs a recorded journey and the authored days that follow it.",
    ),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=Path("docs/evidence"))
    parser.add_argument("--output", type=Path, default=Path("private/reports/video-preview"))
    parser.add_argument(
        "--font", type=Path, default=Path("/System/Library/Fonts/Supplemental/Arial.ttf")
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    normal = str(args.font)
    bold = str(args.font.with_name("Arial Bold.ttf"))
    if not Path(bold).exists():
        bold = normal

    def font(n, strong=False):
        return ImageFont.truetype(bold if strong else normal, n)

    note = json.loads((args.evidence / "journey-teacher-note.json").read_text())
    light = json.loads((args.evidence / "journey-reduce-load.json").read_text())
    script = [
        "# Repaso — 4:40 English narration and captioned preview",
        "",
        "This video reconstructs current synthetic run checkpoints. It is not a "
        "recording of live Telegram or Bedrock. All temporal jumps are labeled. "
        "Record the deployed journey before claiming live execution.",
        "",
    ]
    captions = []

    def stamp(sec):
        return f"{sec // 3600:02}:{sec // 60 % 60:02}:{sec % 60:02},000"

    for i, (title, kicker, stage, caption) in enumerate(SCENES):
        im = Image.new("RGB", (1920, 1080), "#f5f6ef")
        d = ImageDraw.Draw(im)

        def text(value, x, y, width, size=32, color="#163c35", strong=False, max_lines=20, draw=d):
            face = font(size, strong)
            lines = []
            for paragraph in value.splitlines():
                line = ""
                for word in paragraph.split():
                    new = (line + " " + word).strip()
                    if draw.textlength(new, font=face) > width and line:
                        lines.append(line)
                        line = word
                    else:
                        line = new
                lines.append(line)
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                lines[-1] = lines[-1].rstrip(" .") + "…"
            for line in lines:
                draw.text((x, y), line, font=face, fill=color)
                y += int(size * 1.35)
            return y

        d.rounded_rectangle((60, 44, 147, 131), radius=24, fill="#17624f")
        text("r.", 81, 48, 60, 62, "white", True)
        text("REPASO", 172, 64, 500, 36, strong=True)
        text("SIMULATION RECONSTRUCTION • NOT A LIVE RECORDING", 790, 70, 1060, 25, "#506c62")
        text(kicker.upper(), 70, 180, 750, 24, "#337b61", True)
        text(title, 70, 245, 750, 61, strong=True, max_lines=4)
        c = (light if i == 10 else note)["checkpoints"][stage]
        if i == 11:
            summary = (
                "Telegram → webhook → EventBridge → SQS\n\nWorker → AgentCore → Strands\n\n"
                "DynamoDB / S3 / Bedrock / Textract\n\nPending work + outbox + atomic outcomes"
            )
        elif i == 12:
            summary = (
                "10 complete adapter simulations\n\n30 synthetic students / 14 days\n"
                "420 local sessions / 1,037 responses\n\nActual OCR: printed Spanish page\n\n"
                "Independent teacher labels: pending"
            )
        elif i == 7:
            summary = "Earlier in the journey: a source is rejected"
        elif i == 13:
            summary = (
                "localhost:8766/judge/\nCode: REPASO-DEMO\n\n1. Run the complete journey\n"
                "2. Explore seven stages\n3. Compare the two choices\n4. Download the evidence"
            )
        else:
            summary = (
                (
                    "9 reviewed answers"
                    if stage >= 4
                    else f"{len([g for g in c['grades'] if not g['quarantined']])} reviewed answers"
                )
                + "\n\n"
                + (
                    "One exercise in the next practice"
                    if i == 10
                    else "The parent has the final decision"
                )
            )
        text(summary, 74, 560, 735, 29, "#4e685f", max_lines=9)
        d.rounded_rectangle(
            (890, 174, 1850, 855), radius=24, fill="#e5eee3", outline="#cedacb", width=2
        )
        text(
            "TECHNICAL CONTEXT AND LIMITS" if i >= 11 else "OUTPUT FROM THE SYNTHETIC RUN",
            921,
            198,
            890,
            22,
            "#527667",
            True,
        )
        entries = [e for e in c["transcript"] if e.get("speaker") and e.get("text")]
        if i in [0, 2]:
            messages = [
                (
                    "School page",
                    next(
                        m["parsed_text"]
                        for m in c["materials"]
                        if m.get("parsed_text") and m["status"] != "rejected"
                    ),
                )
            ]
        elif i == 1:
            messages = [
                ("Repaso", next(e["text"] for e in entries if "práctica de 5 a 10" in e["text"]))
            ]
        elif i in (3, 10):
            messages = [(entries[-1]["speaker"], entries[-1]["text"])]
        elif i == 4:
            messages = [
                (e["speaker"], e["text"]) for e in entries if "Ojo con esa regla" in e["text"]
            ]
        elif i == 5:
            messages = [
                (e["speaker"], e["text"]) for e in entries if "Necesito tu ojo" in e["text"]
            ]
        elif i == 7:
            messages = [
                ("Guide rejected", "2/3 = 4/9. Multiplico el de arriba por 2 y el de abajo por 3."),
                (
                    "Repaso",
                    next(e["text"] for e in entries if "no los puedo dar por buenos" in e["text"]),
                ),
            ]
        elif i == 8:
            messages = [
                (e["speaker"], e["text"]) for e in entries if "lleva varios días" in e["text"]
            ]
        elif i == 9:
            messages = [
                (e["speaker"], e["text"])
                for e in entries
                if e["text"].startswith("Nota para la maestra:")
            ]
        elif i == 11:
            messages = [
                (
                    "Runtime evidence",
                    "Four Strands graphs\nIngest · Session · Response · Daily quality\n\nContainer "
                    "startup verified locally.\nCloud deployment acceptance remains pending.",
                )
            ]
        elif i == 12:
            messages = [
                (
                    "Interpretation",
                    "Authored model responses are not live inference.\n\nOCR confidence is not "
                    "grading accuracy.\n\nSynthetic students are not pilot participants.",
                )
            ]
        elif i == 13:
            messages = [
                (
                    "What remains",
                    "Complete deployed journeys.\nCollect independent teacher labels.\n"
                    "Observe families with consent.\nPublish reviewed submission links.",
                )
            ]
        else:
            messages = [(e["speaker"], e["text"]) for e in entries[-2:]]
        y = 250
        for speaker, body in messages[:2]:
            y = text(speaker, 928, y, 875, 22, "#2e785d", True) + 8
            y = text(body, 928, y, 867, 28, max_lines=13 if len(messages) == 1 else 7) + 28
        d.rectangle((0, 894, 1920, 1080), fill="#163c35")
        text(caption, 80, 920, 1730, 32, "#ffffff", max_lines=3)
        d.rectangle((0, 1070, int(1920 * (i + 1) / 14), 1080), fill="#afcb77")
        im.save(args.output / f"frame-{i:02}.png")
        script.extend(
            [
                f"## {stamp(i * 20)[:8]}–{stamp((i + 1) * 20)[:8]} · {title}",
                "",
                caption,
                "",
            ]
        )
        captions.extend([str(i + 1), f"{stamp(i * 20)} --> {stamp((i + 1) * 20)}", caption, ""])
    Path("docs/submission/video-script.md").write_text("\n".join(script))
    Path("docs/submission/captions.en.srt").write_text("\n".join(captions))
    listing = []
    for i in range(14):
        listing.extend([f"file 'frame-{i:02}.png'", "duration 20"])
    listing.append("file 'frame-13.png'")
    (args.output / "frames.txt").write_text("\n".join(listing))
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to encode the preview")
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(args.output / "frames.txt"),
            "-t",
            "280",
            "-vf",
            "fps=24,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-movflags",
            "+faststart",
            str(args.output / "repaso-preview-4m40s.mp4"),
        ],
        check=True,
    )
    print(args.output / "repaso-preview-4m40s.mp4")


if __name__ == "__main__":
    main()
