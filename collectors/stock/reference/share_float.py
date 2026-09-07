"""
限售股解禁采集器（share_float）
"""

from collectors.base import BaseCollector


class ShareFloatCollector(BaseCollector):
    API_NAME = "share_float"
    table_name = "share_float"
    # The same release lot can be announced more than once.  ``ann_date`` is
    # part of the upstream row identity: on 2026-09-07, omitting it collapsed
    # 22,248 distinct rows into 13,275 keys.
    pk_columns = [
        "ts_code",
        "ann_date",
        "float_date",
        "holder_name",
        "share_type",
    ]
