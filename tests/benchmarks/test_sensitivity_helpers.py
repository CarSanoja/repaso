import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
from sensitivity_grid import (
    CONSTANT_MODULES,
    DEFAULTS,
    GRIDS,
    LOW_ARCHETYPES,
    SETTINGS_FIELDS,
    apply_constants,
    job_data_dir,
    pooled_metrics,
    rebind_constant,
)

from repaso.config.settings import Settings
from repaso.core.harness import escalation_triggers, mastery
from repaso.core.orchestration import response_graph
from repaso.schemas.mastery import MasteryLevel
from repaso.simulator import verdicts
from repaso.simulator.cohort import LOW_ABILITY


@pytest.fixture(autouse=True)
def restore_constants():
    saved = {
        (module_name, name): getattr(importlib.import_module(module_name), name)
        for name, module_names in CONSTANT_MODULES.items()
        for module_name in module_names
    }
    yield
    for (module_name, name), value in saved.items():
        setattr(importlib.import_module(module_name), name, value)


def test_classify_reads_struggling_ceiling_at_call_time():
    assert mastery.classify(0.45, 10) is MasteryLevel.DEVELOPING
    touched = rebind_constant("STRUGGLING_CEILING", 0.5, CONSTANT_MODULES["STRUGGLING_CEILING"])
    assert touched == ["repaso.core.harness.mastery"]
    assert mastery.classify(0.45, 10) is MasteryLevel.STRUGGLING


def test_cooldown_rebind_reaches_every_from_import_consumer():
    touched = rebind_constant(
        "DEFAULT_COOLDOWN_DAYS", 3, CONSTANT_MODULES["DEFAULT_COOLDOWN_DAYS"]
    )
    assert len(touched) == 3
    assert escalation_triggers.DEFAULT_COOLDOWN_DAYS == 3
    assert response_graph.DEFAULT_COOLDOWN_DAYS == 3
    assert verdicts.DEFAULT_COOLDOWN_DAYS == 3


def test_patching_only_the_source_module_misses_the_call_site():
    escalation_triggers.DEFAULT_COOLDOWN_DAYS = 99
    assert response_graph.DEFAULT_COOLDOWN_DAYS == DEFAULTS["DEFAULT_COOLDOWN_DAYS"]
    assert verdicts.DEFAULT_COOLDOWN_DAYS == DEFAULTS["DEFAULT_COOLDOWN_DAYS"]


def test_apply_constants_resets_parameters_not_under_test():
    apply_constants("STRUGGLING_CEILING", 0.5)
    assert mastery.STRUGGLING_CEILING == 0.5
    apply_constants("DEFAULT_COOLDOWN_DAYS", 3)
    assert response_graph.DEFAULT_COOLDOWN_DAYS == 3
    assert mastery.STRUGGLING_CEILING == DEFAULTS["STRUGGLING_CEILING"]


def test_defaults_match_the_shipped_values():
    settings = Settings(local_mode=True)
    assert DEFAULTS["escalation_min_samples"] == settings.escalation_min_samples
    assert DEFAULTS["grader_confidence_threshold"] == settings.grader_confidence_threshold
    assert DEFAULTS["STRUGGLING_CEILING"] == mastery.STRUGGLING_CEILING
    assert DEFAULTS["DEFAULT_COOLDOWN_DAYS"] == escalation_triggers.DEFAULT_COOLDOWN_DAYS
    for param, grid in GRIDS.items():
        assert DEFAULTS[param] in grid


def test_low_archetypes_mirror_the_simulator_ledger():
    assert LOW_ARCHETYPES == {archetype.value for archetype in LOW_ABILITY}


def test_every_swept_parameter_has_a_delivery_mechanism():
    assert set(GRIDS) == set(SETTINGS_FIELDS) | set(CONSTANT_MODULES)


def test_every_settings_grid_value_survives_validation():
    for param in SETTINGS_FIELDS:
        for value in GRIDS[param]:
            assert getattr(Settings(local_mode=True, **{param: value}), param) == value


def test_job_data_dir_separates_every_run():
    dirs = {
        job_data_dir("/base", param, value, seed)
        for param, grid in GRIDS.items()
        for value in grid
        for seed in (20260950, 20260951)
    }
    assert len(dirs) == 2 * sum(len(grid) for grid in GRIDS.values())
    assert job_data_dir("/base", "DEFAULT_COOLDOWN_DAYS", 7, 20260950) == Path(
        "/base/DEFAULT_COOLDOWN_DAYS=7/seed-20260950"
    )


def test_pooled_metrics_pools_counts_before_dividing():
    metrics = pooled_metrics(
        [
            {"tp": 8, "fp": 2, "low": 9, "interrupts": 50},
            {"tp": 9, "fp": 0, "low": 9, "interrupts": 60},
            {"tp": 7, "fp": 4, "low": 9, "interrupts": 40},
        ]
    )
    assert metrics["seeds"] == 3
    assert metrics["precision"] == pytest.approx(24 / 30)
    assert metrics["recall"] == pytest.approx(24 / 27)
    assert metrics["p50"] == 50


def test_pooled_metrics_survives_empty_denominators():
    metrics = pooled_metrics([{"tp": 0, "fp": 0, "low": 0, "interrupts": 0}])
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert pooled_metrics([])["p50"] == 0
