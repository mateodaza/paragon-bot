from main import agg_key, aggregate_trades, get_direction, get_taker, notional, ZERO_HASH


def _make_trade(
    coin="para:BTCD",
    side="B",
    px="60.0",
    sz="10.0",
    time_ms=1700000000000,
    tx_hash="0xabc123",
    buyer="0xBUYER",
    seller="0xSELLER",
):
    return {
        "coin": coin,
        "side": side,
        "px": px,
        "sz": sz,
        "time": time_ms,
        "hash": tx_hash,
        "users": [buyer, seller],
    }


# --- Taker extraction ---

def test_taker_buy_side():
    trade = _make_trade(side="B", buyer="0xAlice", seller="0xBob")
    assert get_taker(trade) == "0xAlice"


def test_taker_sell_side():
    trade = _make_trade(side="A", buyer="0xAlice", seller="0xBob")
    assert get_taker(trade) == "0xBob"


# --- Direction ---

def test_direction_buy():
    assert get_direction(_make_trade(side="B")) == "LONG"


def test_direction_sell():
    assert get_direction(_make_trade(side="A")) == "SHORT"


# --- Notional ---

def test_notional_calculation():
    trade = _make_trade(px="60.0", sz="10.0")
    assert notional(trade) == 600.0


def test_notional_fractional():
    trade = _make_trade(px="1234.56", sz="0.5")
    assert abs(notional(trade) - 617.28) < 0.01


# --- Aggregation key ---

def test_agg_key_normal():
    trade = _make_trade()
    key = agg_key(trade)
    assert key is not None
    assert "para:BTCD" in key
    assert "0xabc123" in key


def test_agg_key_zero_hash_returns_none():
    trade = _make_trade(tx_hash=ZERO_HASH)
    assert agg_key(trade) is None


def test_agg_key_differs_by_side():
    t1 = _make_trade(side="B", tx_hash="0xsame")
    t2 = _make_trade(side="A", tx_hash="0xsame")
    assert agg_key(t1) != agg_key(t2)


def test_agg_key_differs_by_coin():
    t1 = _make_trade(coin="para:BTCD", tx_hash="0xsame")
    t2 = _make_trade(coin="para:AVGO", tx_hash="0xsame")
    assert agg_key(t1) != agg_key(t2)


# --- Aggregation ---

def test_aggregate_single_trade():
    trade = _make_trade(px="60.0", sz="10.0")
    agg = aggregate_trades([trade])
    assert agg["coin"] == "para:BTCD"
    assert agg["side"] == "B"
    assert float(agg["sz"]) == 10.0
    assert abs(agg["_notional"] - 600.0) < 0.01


def test_aggregate_multiple_trades():
    trades = [
        _make_trade(px="60.0", sz="5.0", tx_hash="0xsame"),
        _make_trade(px="61.0", sz="5.0", tx_hash="0xsame"),
    ]
    agg = aggregate_trades(trades)
    assert float(agg["sz"]) == 10.0
    expected_notional = 300.0 + 305.0  # 60*5 + 61*5
    assert abs(agg["_notional"] - expected_notional) < 0.01
    vwap = expected_notional / 10.0
    assert abs(float(agg["px"]) - vwap) < 0.01


def test_aggregate_preserves_coin_and_side():
    trades = [
        _make_trade(coin="para:AVGO", side="A"),
        _make_trade(coin="para:AVGO", side="A"),
    ]
    agg = aggregate_trades(trades)
    assert agg["coin"] == "para:AVGO"
    assert agg["side"] == "A"


def test_aggregate_taker_from_first_trade():
    trades = [
        _make_trade(side="B", buyer="0xFirst"),
        _make_trade(side="B", buyer="0xFirst"),
    ]
    agg = aggregate_trades(trades)
    assert agg["_taker"] == "0xFirst"
