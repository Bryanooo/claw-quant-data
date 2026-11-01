import numpy as np
import pandas as pd
import pytest
from service.research.local_factors.market import _last_rolling_mean, _last_rolling_std, _cumulative_return


@pytest.mark.parametrize('window', [5,21,252,1320,1600])
@pytest.mark.parametrize('dtype', ['float32','float64'])
def test_terminal_statistics_match_full_rolling(window,dtype):
    rng=np.random.default_rng(7)
    frame=pd.DataFrame(rng.normal(0,.01,(1400,4))).astype(dtype)
    frame.iloc[-2,1]=np.nan
    frame.iloc[-3,2]=np.inf
    expected_mean=frame.rolling(window,min_periods=window).mean().iloc[-1]
    expected_std=frame.rolling(window,min_periods=window).std(ddof=1).iloc[-1]
    expected_return=frame.add(1).rolling(window,min_periods=window).apply(np.prod,raw=True).sub(1).iloc[-1]
    pd.testing.assert_series_equal(_last_rolling_mean(frame,window),expected_mean,check_names=False,rtol=1e-10,atol=1e-12)
    pd.testing.assert_series_equal(_last_rolling_std(frame,window),expected_std,check_names=False,rtol=1e-10,atol=1e-12)
    # float32 addition precedes pandas' float64 rolling conversion in the original.
    pd.testing.assert_series_equal(_cumulative_return(frame,window),expected_return,check_names=False,rtol=1e-10,atol=1e-12)
