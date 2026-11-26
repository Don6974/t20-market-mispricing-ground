import importlib.util
from pathlib import Path

script = Path(__file__).resolve().parents[1] / 'scripts' / 'final_research_pipeline.py'
spec = importlib.util.spec_from_file_location('final_research_pipeline', script)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_percentile():
    assert mod.percentile([], .5) is None
    assert mod.percentile([0, 10], .5) == 5
    assert mod.percentile([1], .95) == 1


def test_runner_price_probability_moves_and_gaps():
    r = mod.summarize_runner('M', 'R', [
        ('2025-01-01T12:00:00Z', 2.0),
        ('2025-01-01T12:00:00Z', 2.0),
        ('2025-01-01T12:00:05Z', 1.8),
        ('2025-01-01T12:03:05Z', 1.5),
    ])
    assert r['exact_duplicate_rows'] == 1
    assert r['observations'] == 3
    assert r['recorded_price_changes'] == 2
    assert r['max_gap_seconds'] == 180
    assert r['probability_range_pp'] > 16


def test_bad_time_or_price_discarded_and_counted():
    r = mod.summarize_runner('M', 'R', [('not a time', 2.0), ('2025-01-01T12:00:00Z', 1.0)])
    assert r['observations'] == 0
    assert r['invalid_rows'] == 2
