"""Reusable completeness proof for non-paginated date-window endpoints."""

from datetime import date, timedelta

import pandas as pd

from collectors.tushare_raw import (
    IncompleteCollectionError,
    is_provider_verified_empty,
    verify_complete_response,
)
from service.tushare_policy import TusharePolicyRegistry


class AdaptiveDateWindowCollectorMixin:
    """Bisect ambiguous capped windows inside one acquisition node.

    Some Tushare endpoints expose ``start_date``/``end_date`` but no offset.
    A round response count can therefore be either legitimate or silently
    truncated. The safe proof is to split that provider request until every
    leaf is below the suspicious cap. These leaves remain transport requests
    inside the same workflow node; they are not tasks or task instances.
    """

    date_field = "trade_date"

    def fetch(self, **params) -> pd.DataFrame:
        self._partition_scopes: list[dict] = []
        policy = TusharePolicyRegistry().get(self.API_NAME)
        start = self._parse_date(params.get("start_date"))
        end = self._parse_date(params.get("end_date"))
        if start or end:
            if not start or not end:
                raise IncompleteCollectionError(
                    f"{self.API_NAME} requires both start_date and end_date"
                )
            if start > end:
                raise ValueError("start_date must not be later than end_date")
            request = {
                **params,
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            }
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
        provider_empty_reason = None
        try:
            frame = self._as_frame(super().fetch(**params))
        except Exception as exc:
            if not is_provider_verified_empty(self.API_NAME, params, exc):
                raise
            frame = pd.DataFrame()
            provider_empty_reason = str(exc)
        self._verify_returned_dates(frame, start, end)
        try:
            proof = verify_complete_response(
                self.API_NAME, policy, params, len(frame)
            )
        except IncompleteCollectionError as exc:
            if "cap" not in str(exc).lower() or start == end:
                raise
            midpoint = start + timedelta(days=(end - start).days // 2)
            right_start = midpoint + timedelta(days=1)
            left = self._fetch_verified_window(
                {
                    **params,
                    "start_date": start.strftime("%Y%m%d"),
                    "end_date": midpoint.strftime("%Y%m%d"),
                },
                start,
                midpoint,
                policy,
            )
            right = self._fetch_verified_window(
                {
                    **params,
                    "start_date": right_start.strftime("%Y%m%d"),
                    "end_date": end.strftime("%Y%m%d"),
                },
                right_start,
                end,
                policy,
            )
            frames = [item for item in (left, right) if not item.empty]
            if not frames:
                return pd.DataFrame(columns=frame.columns)
            return pd.concat(frames, ignore_index=True)

        evidence = {
            **proof,
            "start_date": start.strftime("%Y%m%d"),
            "end_date": end.strftime("%Y%m%d"),
        }
        if provider_empty_reason:
            evidence.update({
                "provider_verified_empty": True,
                "provider_empty_reason": provider_empty_reason,
            })
        self._partition_scopes.append(evidence)
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

    def _verify_returned_dates(
        self, frame: pd.DataFrame, start: date, end: date
    ) -> None:
        if frame.empty or self.date_field not in frame.columns:
            return
        returned = {
            self._parse_date(value)
            for value in frame[self.date_field].dropna().unique()
        }
        outside = sorted(value for value in returned if value < start or value > end)
        if outside:
            raise IncompleteCollectionError(
                f"{self.API_NAME} ignored the requested date window; response "
                f"contains {self.date_field}={outside[0].isoformat()}"
            )
