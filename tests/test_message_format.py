from utils.discord_bot import format_message


def test_emoji_count_minimum():
    msg = format_message("para:BTCD", "LONG", 50.0, "5", "Paragon Trade!")
    assert msg.count("⚡️") == 1


def test_emoji_count_scales_with_notional():
    msg = format_message("para:BTCD", "LONG", 500.0, "5", "Paragon Trade!")
    assert msg.count("⚡️") == 5


def test_emoji_count_capped():
    msg = format_message("para:BTCD", "LONG", 100_000.0, "5", "Paragon Trade!")
    assert msg.count("⚡️") == 80


def test_ticker_display_btcd():
    msg = format_message("para:BTCD", "LONG", 100.0, "5", "Paragon Trade!")
    assert "BTC.D" in msg
    assert "BTCD" not in msg


def test_ticker_display_others():
    msg = format_message("para:OTHERS", "SHORT", 100.0, "10", "Paragon Trade!")
    assert "OTHERS" in msg


def test_direction_long():
    msg = format_message("para:AVGO", "LONG", 100.0, "3", "Paragon Trade!")
    assert "**Direction:** LONG" in msg


def test_direction_short():
    msg = format_message("para:AVGO", "SHORT", 100.0, "3", "Paragon Trade!")
    assert "**Direction:** SHORT" in msg


def test_leverage_present():
    msg = format_message("para:BTCD", "LONG", 100.0, "5", "Paragon Trade!")
    assert "**Leverage:** 5x" in msg


def test_leverage_decimal():
    msg = format_message("para:BTCD", "LONG", 100.0, "3.2", "Paragon Trade!")
    assert "**Leverage:** 3.2x" in msg


def test_leverage_unknown():
    msg = format_message("para:BTCD", "LONG", 100.0, None, "Paragon Trade!")
    assert "**Leverage:** Unknown" in msg


def test_size_formatting():
    msg = format_message("para:BTCD", "LONG", 12345.67, "5", "Paragon Trade!")
    assert "$12,345.67" in msg


def test_title_trade_activity():
    msg = format_message("para:BTCD", "LONG", 100.0, "5", "Paragon Trade!")
    assert "**Paragon Trade!**" in msg


def test_title_strict_open():
    msg = format_message(
        "para:BTCD", "LONG", 100.0, "5", "New Paragon Position!"
    )
    assert "**New Paragon Position!**" in msg


def test_title_position_increased():
    msg = format_message(
        "para:BTCD", "LONG", 100.0, "5", "Paragon Position Increased!"
    )
    assert "**Paragon Position Increased!**" in msg


def test_title_position_flipped():
    msg = format_message(
        "para:BTCD", "SHORT", 100.0, "5", "Paragon Position Flipped!"
    )
    assert "**Paragon Position Flipped!**" in msg


def test_no_tx_link_by_default():
    msg = format_message(
        "para:BTCD", "LONG", 100.0, "5", "Paragon Trade!", tx_hash="0xabc"
    )
    assert "TX" not in msg
