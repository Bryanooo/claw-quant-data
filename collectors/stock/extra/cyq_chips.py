"""
每日筹码分布采集器（cyq_chips）
"""

from datetime import date, timedelta

import pandas as pd

from collectors.base import BaseCollector
from collectors.tushare_raw import (
    IncompleteCollectionError,
    verify_complete_response,
)
from service.tushare_policy import TusharePolicyRegistry


class CyqChipsCollector(BaseCollector):
    API_NAME = "cyq_chips"
    table_name = "cyq_chips"
    pk_columns = ["ts_code", "trade_date", "price"]
    collector_version = "2"

    def fetch(self, **params) -> pd.DataFrame:
        """Fetch one provably complete date scope.

        A legitimate multi-day response can contain exactly 2,000 rows, which
        is indistinguishable from a silent response cap. In that case, discard
        the ambiguous probe and recursively bisect the date range until every
        leaf response is independently below all suspicious caps. Only the
        verified leaf responses are returned to the storage layer.
        """
        self._partition_scopes: list[dict] = []
        policy = TusharePolicyRegistry().get(self.API_NAME)
        start = self._parse_date(params.get("start_date"))
        end = self._parse_date(params.get("end_date"))
        if start or end:
            if not start or not end:
                raise IncompleteCollectionError(
                    "cyq_chips requires both start_date and end_date"
                )
            if start > end:
                raise ValueError("start_date must not be later than end_date")
            request = dict(params)
            request["start_date"] = start.strftime("%Y%m%d")
            request["end_date"] = end.strftime("%Y%m%d")
            return self._fetch_verified_window(request, start, end, policy)

        frame = self._as_frame(super().fetch(**params))
        proof = verify_complete_response(
            self.API_NAME, policy, params, len(frame)
        )
        self._partition_scopes.append({**proof, "parameters": dict(params)})
        return frame

    def _fetch_verified_window(
        self,
        params: dict,
        start: date,
        end: date,
        policy,
    ) -> pd.DataFrame:
        frame = self._as_frame(super().fetch(**params))
        self._verify_returned_dates(frame, start, end)
        try:
            proof = verify_complete_response(
                self.API_NAME, policy, params, len(frame)
            )
        except IncompleteCollectionError as exc:
            if "cap" not in str(exc).lower() or start == end:
                raise
            midpoint = start + timedelta(days=(end - start).days // 2)
            left_params = {
                **params,
                "start_date": start.strftime("%Y%m%d"),
                "end_date": midpoint.strftime("%Y%m%d"),
            }
            right_start = midpoint + timedelta(days=1)
            right_params = {
                **params,
                "start_date": right_start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            }
            left = self._fetch_verified_window(
                left_params, start, midpoint, policy
            )
            right = self._fetch_verified_window(
                right_params, right_start, end, policy
            )
            frames = [item for item in (left, right) if not item.empty]
            if not frames:
                return pd.DataFrame(columns=frame.columns)
            return pd.concat(frames, ignore_index=True)

        self._partition_scopes.append(
            {
                **proof,
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            }
        )
        return frame

    def partition_completion_evidence(self) -> dict:
        scopes = list(getattr(self, "_partition_scopes", ()))
        verified = bool(scopes) and all(item.get("verified") for item in scopes)
        return {
            "verified": verified,
            "verification_type": "adaptive_date_window_exhaustion",
            "scopes": scopes,
            "leaf_scopes": len(scopes),
            "rows_fetched": sum(
                int(item.get("rows_fetched") or 0) for item in scopes
            ),
        }

    @staticmethod
    def _parse_date(value) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date):
            return value
        compact = str(value).replace("-", "")
        if len(compact) != 8 or not compact.isdigit():
            raise ValueError("dates must use YYYYMMDD or YYYY-MM-DD")
        return date(int(compact[:4]), int(compact[4:6]), int(compact[6:]))

    @staticmethod
    def _as_frame(frame) -> pd.DataFrame:
        return frame if frame is not None else pd.DataFrame()

    @staticmethod
    def _verify_returned_dates(frame: pd.DataFrame, start: date, end: date) -> None:
        if frame.empty or "trade_date" not in frame.columns:
            return
        returned = {
            CyqChipsCollector._parse_date(value)
            for value in frame["trade_date"].dropna().unique()
        }
        outside = sorted(value for value in returned if value < start or value > end)
        if outside:
            raise IncompleteCollectionError(
                "cyq_chips ignored the requested date window; response contains "
                f"trade_date={outside[0].isoformat()}"
            )
