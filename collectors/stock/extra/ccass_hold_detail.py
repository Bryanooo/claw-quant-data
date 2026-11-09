"""
中央结算系统持股明细采集器（ccass_hold_detail）
采集策略：按 trade_date 逐天拉
注意：此接口不支持 start_date+end_date 范围查询，必须逐日采集
"""

from collectors.base import BaseCollector


class CcassHoldDetailCollector(BaseCollector):
    API_NAME = "ccass_hold_detail"
    table_name = "ccass_hold_detail"
    pk_columns = ["ts_code", "trade_date", "participant_key"]
    supports_range_query = False  # 不支持范围查询，需逐日拉取

    def fetch(self, **params):
        if (not str(params.get('ts_code', '')).endswith('.HK') or not params.get('trade_date')
                or 'start_date' in params or 'end_date' in params):
            raise ValueError('ccass_hold_detail requires one HK security and an exact trading date')
        frame = super().fetch(**params)
        if not frame.empty and (set(frame.ts_code) != {params['ts_code']} or
                set(frame.trade_date.astype(str)) != {params['trade_date']}):
            raise ValueError('CCASS provider response does not match request')
        return frame

    def transform(self, df):
        if df.empty:
            return df
        frame = df.drop_duplicates().copy()
        ids = frame.col_participant_id.fillna('').astype(str)
        names = frame.col_participant_name.fillna('').astype(str)
        if ((ids.str.strip() == '') & (names.str.strip() == '')).any():
            raise ValueError('CCASS participant has neither ID nor name')
        frame['participant_key'] = ('id:' + ids).where(ids.str.strip() != '', 'name:' + names)
        if frame.duplicated(self.pk_columns).any():
            raise ValueError('conflicting CCASS rows for one participant on the same date')
        return frame
