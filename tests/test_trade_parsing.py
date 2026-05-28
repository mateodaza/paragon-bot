from main import (
    agg_key,
    aggregate_trades,
    classify_position,
    get_direction,
    get_taker,
    notional,
    validate_trade,
    ZERO_HASH,
)


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


# --- Trade validation ---

def test_validate_trade_valid_buy():
    assert validate_trade(_make_trade(side="B")) is True


def test_validate_trade_valid_sell():
    assert validate_trade(_make_trade(side="A")) is True


def test_validate_trade_invalid_side():
    assert validate_trade(_make_trade(side="X")) is False


def test_validate_trade_missing_side():
    trade = _make_trade()
    del trade["side"]
    assert validate_trade(trade) is False


def test_validate_trade_wrong_users_count():
    trade = _make_trade()
    trade["users"] = ["0xOnly"]
    assert validate_trade(trade) is False


def test_validate_trade_empty_users():
    trade = _make_trade()
    trade["users"] = []
    assert validate_trade(trade) is False


# --- Position classification (strict_open) ---

def test_classify_open_long_from_flat():
    assert classify_position("Open Long", "0.0") == "New Paragon Position!"


def test_classify_open_short_from_flat():
    assert classify_position("Open Short", "0.0") == "New Paragon Position!"


def test_classify_open_long_from_zero():
    assert classify_position("Open Long", "0") == "New Paragon Position!"


def test_classify_open_long_adding():
    assert classify_position("Open Long", "500.0") == "Paragon Position Increased!"


def test_classify_open_short_adding():
    assert classify_position("Open Short", "200.0") == "Paragon Position Increased!"


def test_classify_flip_long_to_short():
    assert classify_position("Long > Short", "500.0") == "Paragon Position Flipped!"


def test_classify_flip_short_to_long():
    assert classify_position("Short > Long", "300.0") == "Paragon Position Flipped!"


def test_classify_close_long_skipped():
    assert classify_position("Close Long", "500.0") is None


def test_classify_close_short_skipped():
    assert classify_position("Close Short", "500.0") is None


def test_classify_none_fill_skipped():
    assert classify_position(None, "") is None


def test_classify_unknown_dir_skipped():
    assert classify_position("SomeNewDir", "0.0") is None
