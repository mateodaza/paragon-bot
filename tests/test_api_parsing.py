from utils.hyperliquid_api import match_fill, parse_leverage_response


# --- Leverage response parsing ---

def test_leverage_found():
    state = {
        "assetPositions": [
            {
                "position": {
                    "coin": "para:BTCD",
                    "leverage": {"value": "20"},
                }
            }
        ]
    }
    assert parse_leverage_response(state, "para:BTCD") == "20"


def test_leverage_decimal():
    state = {
        "assetPositions": [
            {
                "position": {
                    "coin": "para:AVGO",
                    "leverage": {"value": "3.2"},
                }
            }
        ]
    }
    assert parse_leverage_response(state, "para:AVGO") == "3.2"


def test_leverage_wrong_coin():
    state = {
        "assetPositions": [
            {
                "position": {
                    "coin": "para:BTCD",
                    "leverage": {"value": "5"},
                }
            }
        ]
    }
    assert parse_leverage_response(state, "para:OTHERS") is None


def test_leverage_no_positions():
    assert parse_leverage_response({"assetPositions": []}, "para:BTCD") is None


def test_leverage_missing_key():
    assert parse_leverage_response({}, "para:BTCD") is None


def test_leverage_missing_leverage_field():
    state = {
        "assetPositions": [
            {"position": {"coin": "para:BTCD"}}
        ]
    }
    assert parse_leverage_response(state, "para:BTCD") is None


def test_leverage_multiple_positions():
    state = {
        "assetPositions": [
            {"position": {"coin": "para:AVGO", "leverage": {"value": "5"}}},
            {"position": {"coin": "para:BTCD", "leverage": {"value": "20"}}},
        ]
    }
    assert parse_leverage_response(state, "para:BTCD") == "20"


# --- Fill matching ---

def test_match_fill_found():
    fills = [
        {
            "coin": "para:BTCD",
            "hash": "0xabc",
            "side": "B",
            "dir": "Open Long",
            "startPosition": "0.0",
        }
    ]
    result = match_fill(fills, "para:BTCD", "0xabc", "B")
    assert result is not None
    assert result["dir"] == "Open Long"
    assert result["start_position"] == "0.0"


def test_match_fill_wrong_coin():
    fills = [
        {"coin": "para:AVGO", "hash": "0xabc", "side": "B", "dir": "Open Long", "startPosition": "0.0"}
    ]
    assert match_fill(fills, "para:BTCD", "0xabc", "B") is None


def test_match_fill_wrong_hash():
    fills = [
        {"coin": "para:BTCD", "hash": "0xdef", "side": "B", "dir": "Open Long", "startPosition": "0.0"}
    ]
    assert match_fill(fills, "para:BTCD", "0xabc", "B") is None


def test_match_fill_wrong_side():
    fills = [
        {"coin": "para:BTCD", "hash": "0xabc", "side": "A", "dir": "Open Short", "startPosition": "0.0"}
    ]
    assert match_fill(fills, "para:BTCD", "0xabc", "B") is None


def test_match_fill_empty_list():
    assert match_fill([], "para:BTCD", "0xabc", "B") is None


def test_match_fill_none_list():
    assert match_fill(None, "para:BTCD", "0xabc", "B") is None


def test_match_fill_multiple_picks_correct():
    fills = [
        {"coin": "para:AVGO", "hash": "0xabc", "side": "B", "dir": "Close Long", "startPosition": "100.0"},
        {"coin": "para:BTCD", "hash": "0xabc", "side": "B", "dir": "Open Long", "startPosition": "0.0"},
    ]
    result = match_fill(fills, "para:BTCD", "0xabc", "B")
    assert result["dir"] == "Open Long"


def test_match_fill_nonzero_start_position():
    fills = [
        {"coin": "para:BTCD", "hash": "0xabc", "side": "A", "dir": "Open Short", "startPosition": "500.0"}
    ]
    result = match_fill(fills, "para:BTCD", "0xabc", "A")
    assert result["start_position"] == "500.0"
