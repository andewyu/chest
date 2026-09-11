import pytest

from scripts import cache_grants


def test_cache_command_rejects_zero_rows_before_overwriting(monkeypatch):
    monkeypatch.setattr("sys.argv", ["cache_grants", "--rows", "0"])
    monkeypatch.setattr(
        cache_grants.gg,
        "save_cache",
        lambda _: pytest.fail("an invalid run must not overwrite the cache"),
    )

    with pytest.raises(SystemExit):
        cache_grants.main()
