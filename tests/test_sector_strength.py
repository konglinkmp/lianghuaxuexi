import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from quant.sector_strength import SectorStrengthFilter


def test_sector_strength_filter_require_both():
    filt = SectorStrengthFilter(
        strong_industries={"半导体"},
        strong_concepts={"AI"},
    )

    assert filt.is_allowed("半导体", ["AI"], layer="AGGRESSIVE") is True
    assert filt.is_allowed("半导体", ["新能源"], layer="AGGRESSIVE") is False
    assert filt.is_allowed("地产", ["AI"], layer="AGGRESSIVE") is False
