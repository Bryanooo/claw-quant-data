from service.notifiers.dingtalk import DingtalkNotifier
from service.tools.stock import daily


def test_get_daily_builds_parameterized_query(monkeypatch):
    captured = {}

    def fake_query(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return [{"ts_code": "000001.SZ"}]

    monkeypatch.setattr(daily, "query", fake_query)

    rows = daily.get_daily("000001.SZ", "20260101", "20260131")

    assert rows == [{"ts_code": "000001.SZ"}]
    assert captured["params"] == ("000001.SZ", "20260101", "20260131")
    assert "%s" in captured["sql"]
    assert "000001.SZ" not in captured["sql"]


def test_dingtalk_notifier_requires_user_id(monkeypatch):
    monkeypatch.setattr(
        "service.notifiers.dingtalk.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("subprocess must not be called")
        ),
    )

    assert DingtalkNotifier(user_id=None).send("test") is False
