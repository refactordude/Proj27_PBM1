"""UFS 시드 픽스처 — ship-bar E2E 테스트용 소형 데이터셋.

세 개의 빌더 함수는 실제 ufs_data 테이블이 반환할 법한 long-form 행을
pd.DataFrame으로 만들어 돌려준다. 컬럼은 (PLATFORM_ID, InfoCategory , Item,
Result)
"""
from __future__ import annotations

import pandas as pd

_COLS = ["PLATFORM_ID", "InfoCategory", "Item", "Result"]


def wb_enable_rows() -> pd.DataFrame:
    """SHIP-01: wb_enable 값을 디바이스별로 비교하는 시나리오용."""
    return pd.DataFrame(
        [
            ("SM-S918", "Feature", "wb_enable", "0x1"),
            ("SM-G998", "Feature", "wb_enable", "0x0"),
            ("OPPO-FIND-X6", "Feature", "wb_enable", "None"),
            ("PIXEL-8", "Feature", "wb_enable", "1"),
            ("IQOO-12", "Feature", "wb_enable", "0x1"),
        ],
        columns=_COLS,
    )


def capacity_rows() -> pd.DataFrame:
    """SHIP-02: total_raw_device_capacity 를 디바이스별로 비교하는 시나리오용."""
    return pd.DataFrame(
        [
            ("SM-S918", "Capacity", "total_raw_device_capacity", "0x1D1C0000000"),
            ("SM-G998", "Capacity", "total_raw_device_capacity", "0xEE600000"),
            ("OPPO-FIND-X6", "Capacity", "total_raw_device_capacity", "128849018880"),
            ("PIXEL-8", "Capacity", "total_raw_device_capacity", "None"),
            ("IQOO-12", "Capacity", "total_raw_device_capacity", "0xEE600000"),
        ],
        columns=_COLS,
    )


def lifetime_samsung_oppo_rows() -> pd.DataFrame:
    """SHIP-03: life_time_estimation_a 를 Samsung/OPPO 두 브랜드로 비교하는 시나리오용."""
    return pd.DataFrame(
        [
            ("SM-S918", "Lifetime", "life_time_estimation_a", "0x01"),
            ("SM-G998", "Lifetime", "life_time_estimation_a", "0x02"),
            ("OPPO-FIND-X6", "Lifetime", "life_time_estimation_a", "local=1,peer=2"),
            ("OPPO-RENO-11", "Lifetime", "life_time_estimation_a", "0x03"),
        ],
        columns=_COLS,
    )
