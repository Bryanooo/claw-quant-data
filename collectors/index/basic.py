"""
指数基本信息采集器
接口：index_basic（tushare pro）

说明：
  获取各类指数的基本信息，包括代码、名称、发布方、指数类型、币种等。
  market 参数可以用 "SSE" / "SZSE" 等限定交易所，或留空获取全部。
"""

import pandas as pd
from collectors.base import BaseCollector
from collectors.tushare_raw import IncompleteCollectionError


class IndexBasicCollector(BaseCollector):
    """指数基本信息采集器"""

    API_NAME = "index_basic"
    table_name = "index_basic"
    pk_columns = ["ts_code"]
    collector_version = "2"

    # The upstream contract documents seven markets.  Live responses also
    # contain CNI and BSE records, so they are retained as observed extensions
    # instead of silently disappearing from the snapshot.
    MARKETS = (
        "SSE", "SZSE", "CSI", "MSCI", "CICC", "SW", "OTH", "CNI", "BSE",
    )
    # index_basic is capped at 8,000 rows. CSI alone now exceeds that limit,
    # therefore its finite, documented category vocabulary is the safe second
    # partition dimension. The two additional values are already emitted by
    # the live endpoint and are included explicitly.
    CSI_CATEGORIES = (
        "主题指数", "规模指数", "策略指数", "风格指数", "综合指数", "成长指数",
        "价值指数", "有色指数", "化工指数", "能源指数", "其他指数", "外汇指数",
        "基金指数", "商品指数", "债券指数", "行业指数", "贵金属指数",
        "农副产品指数", "软商品指数", "油脂油料指数", "非金属建材指数",
        "煤焦钢矿指数", "谷物指数", "多资产指数", "期货指数",
    )
    RESPONSE_LIMIT = 8_000

    def validate_response(self, df: pd.DataFrame, parameters: dict) -> None:
        if len(df) >= self.RESPONSE_LIMIT:
            raise IncompleteCollectionError(
                f"index_basic response reached the {self.RESPONSE_LIMIT}-row limit; "
                "use the full market/category snapshot"
            )
        market = parameters.get("market")
        if market and not df.empty and set(df["market"].dropna()) != {market}:
            raise IncompleteCollectionError(
                f"index_basic ignored the market partition {market}"
            )
        category = parameters.get("category")
        if category and not df.empty and set(df["category"].dropna()) != {category}:
            raise IncompleteCollectionError(
                f"index_basic ignored the category partition {category}"
            )

    def collect(self, market: str = None, **kwargs) -> int:
        """
        采集指数基本信息。

        参数：
          market: 交易所 SSE/SZSE/ALL（空则全量）
        """
        if market:
            return super().collect(market=market, **kwargs)
        if kwargs:
            raise ValueError("full index_basic snapshot does not accept extra parameters")
        return self.collect_full_snapshot()

    def _checked_fetch(self, *, market: str, category: str | None = None) -> pd.DataFrame:
        params = {"market": market}
        if category is not None:
            params["category"] = category
        frame = self.fetch(**params)
        if frame is None:
            frame = pd.DataFrame()
        if len(frame) >= self.RESPONSE_LIMIT:
            scope = f"market={market}" + (f", category={category}" if category else "")
            raise IncompleteCollectionError(
                f"index_basic response reached the {self.RESPONSE_LIMIT}-row limit "
                f"for {scope}; refusing an incomplete snapshot"
            )
        self.validate_response(frame, params)
        return frame

    def collect_full_snapshot(self) -> int:
        """Collect every market with a bounded CSI category partition.

        The assembled frame is written atomically. Any capped/ignored
        partition fails before storage, so a bad upstream response cannot
        replace the last known-good reference snapshot.
        """
        frames: list[pd.DataFrame] = []
        for market in self.MARKETS:
            if market != "CSI":
                frame = self._checked_fetch(market=market)
                if not frame.empty:
                    frames.append(frame)
                continue

            # The unfiltered response is intentionally used only as a bounded
            # discovery sample. It is never stored or mistaken for complete.
            sample = self.fetch(market="CSI")
            if sample is None:
                sample = pd.DataFrame()
            categories = set(self.CSI_CATEGORIES)
            if not sample.empty and "category" in sample:
                categories.update(str(value) for value in sample["category"].dropna())
            if not sample.empty and sample.get("category", pd.Series(dtype=object)).isna().any():
                raise IncompleteCollectionError(
                    "index_basic CSI sample contains rows without category; "
                    "the configured category partition cannot prove completeness"
                )
            csi_frames = [
                self._checked_fetch(market="CSI", category=category)
                for category in sorted(categories)
            ]
            csi_frames = [frame for frame in csi_frames if not frame.empty]
            if sample is not None and not sample.empty:
                sampled_codes = set(sample["ts_code"])
                collected_codes = {
                    code for frame in csi_frames for code in frame["ts_code"].tolist()
                }
                if not sampled_codes <= collected_codes:
                    raise IncompleteCollectionError(
                        "index_basic CSI category partitions do not contain the "
                        "complete unfiltered discovery sample"
                    )
            frames.extend(csi_frames)

        if not frames:
            raise IncompleteCollectionError("index_basic full snapshot returned no rows")
        snapshot = self.transform(pd.concat(frames, ignore_index=True))
        snapshot = snapshot.drop_duplicates(subset=self.pk_columns, keep="last")
        return self.store_snapshot(snapshot)
