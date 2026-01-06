import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from quant.style_benchmark import compute_style_weights


def test_compute_style_weights():
    caps = {"a": 200_000_000_000, "b": 50_000_000_000, "c": 10_000_000_000}
    thresholds = {"large": 100_000_000_000, "mid": 30_000_000_000}
    bucket_map = {"large": "hs300", "mid": "csi500", "small": "csi1000"}
    default = {"hs300": 0.5, "csi1000": 0.5}

    weights = compute_style_weights(caps, thresholds, bucket_map, default)
    total = sum(weights.values())
    assert round(total, 6) == 1.0
    assert weights["hs300"] > weights["csi500"] > weights["csi1000"]
