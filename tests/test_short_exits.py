"""Regression tests for the short side.

A short used to have exactly one exit: SHORT_TAKE_PROFIT. There was no stop loss
and no time stop (both were deliberately disabled in code), the documented
"close early on a bullish signal" branch was unreachable, and margin rollover
fees were not modelled anywhere. On a 2x leveraged position that combination is
strictly worse than the long-side bug it mirrored.
"""

import time

import pytest

from trading_bot import PROTECTIVE_EXIT_REASONS, TradingBot


class APIMock:
    def get_ohlc_data(self, pair, interval, since=None):
        return {pair: [[0, 0, 0, 0, 100, 0, 0, 0]] * 30}

    def query_public(self, *a, **k):
        return {}

    def get_asset_pairs(self):
        return {'XBTEUR': {'altname': 'XBTEUR', 'wsname': 'XBT/EUR'}}

    def get_account_balance(self):
        return {}

    def get_open_orders(self):
        return {}

    def get_trade_history(self, *a, **k):
        return {}


def make_bot(**shorting_overrides):
    shorting = {
        'enabled': True,
        'leverage': '2',
        'short_take_profit_percent': 1.26,
        'short_stop_loss_percent': 3.0,
        'enable_short_hard_stop': True,
        'enable_short_time_stop': True,
        'short_time_stop_hours': 24.0,
        'rollover_fee_percent_per_4h': 0.02,
    }
    shorting.update(shorting_overrides)
    cfg = {
        'bot_settings': {'trade_pairs': ['XBTEUR'], 'trade_amounts': {'trade_amount_eur': 30.0}},
        'risk_management': {
            'min_net_sell_profit_pct': 0.7,
            'exit_slippage_buffer_pct': 0.35,
            'fees_maker_percent': 0.16,
            'fees_taker_percent': 0.26,
        },
        'shorting': shorting,
    }
    bot = TradingBot(APIMock(), cfg)
    bot.trade_pairs = ['XBTEUR']
    return bot


def open_short(bot, entry=100.0, qty=1.0, age_hours=0.0):
    bot.short_qty['XBTEUR'] = qty
    bot.short_entry_prices['XBTEUR'] = entry
    bot.short_entry_timestamps['XBTEUR'] = time.time() - age_hours * 3600
    bot.holdings['XBTEUR'] = 0.0


# --- stops must exist at all ------------------------------------------------

def test_short_hard_stop_fires_when_price_rises():
    bot = make_bot()
    open_short(bot, entry=100.0)
    bot.pair_prices['XBTEUR'] = 104.0  # short is 4% under water
    pair, reason, change = bot.check_take_profit_or_stop_loss()
    assert (pair, reason) == ('XBTEUR', 'SHORT_HARD_STOP')
    assert change == pytest.approx(-4.0, abs=0.01)


def test_short_hard_stop_bypasses_the_profit_gate():
    assert 'SHORT_HARD_STOP' in PROTECTIVE_EXIT_REASONS
    assert 'SHORT_TIME_STOP' in PROTECTIVE_EXIT_REASONS


def test_short_time_stop_fires_on_stale_position():
    bot = make_bot(enable_short_hard_stop=False)
    open_short(bot, entry=100.0, age_hours=25.0)
    bot.pair_prices['XBTEUR'] = 100.5  # small loss, well inside the hard stop
    pair, reason, _ = bot.check_take_profit_or_stop_loss()
    assert (pair, reason) == ('XBTEUR', 'SHORT_TIME_STOP')


def test_short_take_profit_still_wins_over_stops():
    bot = make_bot()
    open_short(bot, entry=100.0, age_hours=48.0)
    bot.pair_prices['XBTEUR'] = 98.0  # +2% in our favour
    pair, reason, _ = bot.check_take_profit_or_stop_loss()
    assert (pair, reason) == ('XBTEUR', 'SHORT_TAKE_PROFIT')


def test_stops_still_run_after_shorting_is_disabled():
    """Turning the feature off must not strand an already-open position."""
    bot = make_bot(enabled=False)
    assert bot.enable_live_shorts is False
    open_short(bot, entry=100.0)
    bot.pair_prices['XBTEUR'] = 104.0
    pair, reason, _ = bot.check_take_profit_or_stop_loss()
    assert (pair, reason) == ('XBTEUR', 'SHORT_HARD_STOP')


def test_healthy_short_is_left_alone():
    bot = make_bot()
    open_short(bot, entry=100.0, age_hours=2.0)
    bot.pair_prices['XBTEUR'] = 99.5  # small gain, below TP
    assert bot.check_take_profit_or_stop_loss() == (None, None, None)


# --- rollover fees ----------------------------------------------------------

def test_rollover_cost_grows_with_holding_time():
    bot = make_bot()
    open_short(bot, age_hours=0.0)
    assert bot._short_rollover_cost_pct('XBTEUR') == pytest.approx(0.02)

    open_short(bot, age_hours=10.0)  # 1 + 10//4 = 3 periods
    assert bot._short_rollover_cost_pct('XBTEUR') == pytest.approx(0.06)

    open_short(bot, age_hours=48.0)  # 1 + 12 = 13 periods
    assert bot._short_rollover_cost_pct('XBTEUR') == pytest.approx(0.26)


def test_rollover_is_deducted_from_the_net_profit_gate():
    """A gain that clears the gate when fresh must fail it once fees pile up."""
    bot = make_bot()
    price = 98.0  # ~2% gross in our favour

    open_short(bot, entry=100.0, age_hours=0.0)
    bot.pair_prices['XBTEUR'] = price
    assert bot._can_close_short_profit_target('XBTEUR', price) is True

    # Same price, but held for weeks — rollover has eaten the edge.
    open_short(bot, entry=100.0, age_hours=24 * 20)
    bot.pair_prices['XBTEUR'] = price
    assert bot._can_close_short_profit_target('XBTEUR', price) is False


def test_rollover_disabled_when_rate_is_zero():
    bot = make_bot(rollover_fee_percent_per_4h=0.0)
    open_short(bot, age_hours=100.0)
    assert bot._short_rollover_cost_pct('XBTEUR') == 0.0


# --- restart safety ---------------------------------------------------------

def test_persisted_short_is_restored_as_a_short(tmp_path):
    """A short used to come back as a phantom long after a restart."""
    import json

    bot = make_bot()
    state = tmp_path / 'purchase_prices.json'
    state.write_text(json.dumps({
        'XBTEUR': {
            'pair': 'XBTEUR', 'side': 'short', 'qty': 0.5,
            'entry_price_eur': 100.0, 'fees_eur': 0.0,
            'notional_eur': 50.0, 'entry_ts': int(time.time()) - 3600,
        }
    }))
    bot.data_purchase_prices_path = str(state)
    bot.purchase_prices.clear()
    bot.short_qty.clear()
    bot._sync_account_state()

    assert bot.short_qty.get('XBTEUR') == 0.5
    assert bot.short_entry_prices.get('XBTEUR') == 100.0
    assert bot.short_entry_timestamps.get('XBTEUR')
    # and it must NOT have been restored as a long
    assert not bot.purchase_prices.get('XBTEUR')
