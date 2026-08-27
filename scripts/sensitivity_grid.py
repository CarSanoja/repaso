import importlib
from pathlib import Path

SETTINGS_FIELDS = ("escalation_min_samples", "grader_confidence_threshold")
CONSTANT_MODULES = {
    "STRUGGLING_CEILING": ("repaso.core.harness.mastery",),
    "DEFAULT_COOLDOWN_DAYS": (
        "repaso.core.harness.escalation_triggers",
        "repaso.core.orchestration.response_graph",
        "repaso.simulator.verdicts",
    ),
}
GRIDS = {
    "escalation_min_samples": [5, 6, 7, 8, 9, 10, 12],
    "STRUGGLING_CEILING": [0.3, 0.325, 0.35, 0.375, 0.4, 0.425, 0.45, 0.475, 0.5],
    "DEFAULT_COOLDOWN_DAYS": [3, 5, 7, 10, 14],
    "grader_confidence_threshold": [0.7, 0.8, 0.85, 0.9, 0.95],
}
DEFAULTS = {
    "escalation_min_samples": 8,
    "STRUGGLING_CEILING": 0.4,
    "DEFAULT_COOLDOWN_DAYS": 7,
    "grader_confidence_threshold": 0.85,
}
LOW_ARCHETYPES = {"struggling", "cohort_cluster"}
TOLERANCE = 0.03
RECALL_FLOOR = 0.95
HEAD = f"{'value':>8} {'precision':>10} {'recall':>8} {'p50':>5} {'tp':>5} {'fp':>4}  flag"


def rebind_constant(name: str, value: float, module_names: tuple[str, ...]) -> list[str]:
    touched = []
    for module_name in module_names:
        module = importlib.import_module(module_name)
        if hasattr(module, name):
            setattr(module, name, value)
            touched.append(module_name)
    return touched


def apply_constants(param: str, value: float) -> dict[str, list[str]]:
    return {
        name: rebind_constant(name, value if name == param else DEFAULTS[name], modules)
        for name, modules in CONSTANT_MODULES.items()
    }


def job_data_dir(base_dir: str, param: str, value: float, seed: int) -> Path:
    return Path(base_dir) / f"{param}={value}" / f"seed-{seed}"


def pooled_metrics(rows: list[dict]) -> dict:
    tp = sum(row["tp"] for row in rows)
    fp = sum(row["fp"] for row in rows)
    low = sum(row["low"] for row in rows)
    interrupts = sorted(row["interrupts"] for row in rows)
    return {
        "seeds": len(rows), "tp": tp, "fp": fp, "low": low,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / low if low else 0.0,
        "p50": interrupts[len(interrupts) // 2] if interrupts else 0,
    }


def plateau_span(
    points: list[dict], tolerance: float = TOLERANCE, recall_floor: float = RECALL_FLOOR
) -> tuple[int, int] | None:
    if not points:
        return None
    ceiling = max(point["precision"] for point in points)
    flags = [
        point["precision"] >= ceiling - tolerance - 1e-9 and point["recall"] >= recall_floor - 1e-9
        for point in points
    ]
    best, start = None, None
    for index, flag in enumerate([*flags, False]):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            if best is None or index - start > best[1] - best[0] + 1:
                best = (start, index - 1)
            start = None
    return best


def plateau_verdict(param: str, points: list[dict], span: tuple[int, int] | None) -> str:
    values = [point["value"] for point in points]
    default = DEFAULTS[param]
    index = values.index(default)
    if span is None:
        return f"{param}: NO PLATEAU (no value clears the floors); default {default} OUTSIDE"
    if not span[0] <= index <= span[1]:
        place = "OUTSIDE"
    else:
        place = "INSIDE (interior)" if span[0] < index < span[1] else "INSIDE (edge)"
    width, where = f"{span[1] - span[0] + 1}/{len(values)} values", f"default {default} {place}"
    return f"{param}: plateau [{values[span[0]]}, {values[span[1]]}] ({width}); {where}"


def format_table(param: str, points: list[dict], span: tuple[int, int] | None) -> str:
    lines = [f"{param}  ({len(points)} values x {points[0]['seeds']} seeds)", HEAD]
    for index, point in enumerate(points):
        flags = []
        if span is not None and span[0] <= index <= span[1]:
            flags.append("plateau")
        if point["value"] == DEFAULTS[param]:
            flags.append("DEFAULT")
        lines.append(
            f"{point['value']!s:>8} {point['precision']:>10.3f} {point['recall']:>8.3f}"
            f" {point['p50']:>5} {point['tp']:>5} {point['fp']:>4}  {' '.join(flags)}"
        )
    return "\n".join(lines)


def summarize(rows: list[dict], params: list[str]) -> dict:
    report = {}
    for param in params:
        points = []
        for value in GRIDS[param]:
            subset = [r for r in rows if r["param"] == param and r["value"] == value]
            points.append({**pooled_metrics(subset), "value": value})
        span = plateau_span(points)
        report[param] = {
            "points": points,
            "span": list(span) if span else None,
            "verdict": plateau_verdict(param, points, span),
        }
    return report


def default_points(report: dict) -> list[dict]:
    return [
        {"param": param, **point}
        for param, block in report.items()
        for point in block["points"]
        if point["value"] == DEFAULTS[param]
    ]


def default_points_agree(rows: list[dict]) -> bool:
    return len({(row["tp"], row["fp"], row["low"], row["p50"]) for row in rows}) <= 1


def format_default_check(rows: list[dict]) -> str:
    head = "identical" if default_points_agree(rows) else "MISMATCH - parameters leaked"
    lines = [f"default-point cross-check ({len(rows)} parameters): {head}"]
    for row in rows:
        lines.append(
            f"{row['param']:>28}={row['value']!s:<6} tp={row['tp']:<5} fp={row['fp']:<4}"
            f" recall={row['recall']:.3f} p50={row['p50']}"
        )
    return "\n".join(lines)
