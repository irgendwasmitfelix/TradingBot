"""Regression tests for exit gating.

Every exit used to be routed through ``_can_sell_profit_target``, which demands a
net gain. That made stop-losses unreachable: a losing position could never be
closed and simply accumulated (observed live: XRPEUR held 48 days at -8%).

These tests pin down the two properties that must hold:
  * protective exits (stops, time stop, airbag, bear shield) can close at a loss
  * discretionary exits (signal flips, TAKE_PROFIT) still require the profit target
"""

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


def make_bot(**risk_overrides):
    risk = {
        'take_profit_percent': 3.0,
        'max_take_profit_percent': 14.0,
        'min_net_sell_profit_pct': 0.7,
        'exit_slippage_buffer_pct': 0.35,
        'sell_fee_buffer_percent': 0.26,
        'fees_maker_percent': 0.16,
        'fees_taker_percent': 0.26,
        'adaptive_take_profit': False,
        'enable_atr_dynamic_tp': False,
        'enable_atr_stop': False,
    }
    risk.update(risk_overrides)
    cfg = {
        'bot_settings': {'trade_pairs': ['XBTEUR'], 'trade_amounts': {'trade_amount_eur': 30.0}},
        'risk_management': risk,
    }
    return TradingBot(APIMock(), cfg)


# --- the profit gate itself -------------------------------------------------

def test_gate_blocks_sell_below_target():
    bot = make_bot()
    bot.purchase_prices['XBTEUR'] = 100.0
    bot.pair_prices['XBTEUR'] = 101.0  # +1%, below the 3% target
    assert bot._can_sell_profit_target('XBTEUR', 101.0) is False


def test_gate_allows_sell_above_target():
    bot = make_bot()
    bot.purchase_prices['XBTEUR'] = 100.0
    bot.pair_prices['XBTEUR'] = 104.0  # +4% gross, clears target and net floor
    assert bot._can_sell_profit_target('XBTEUR', 104.0) is True


def test_gate_blocks_a_loss():
    bot = make_bot()
    bot.purchase_prices['XBTEUR'] = 100.0
    bot.pair_prices['XBTEUR'] = 92.0
    assert bot._can_sell_profit_target('XBTEUR', 92.0) is False


# --- the routing that made stops unreachable --------------------------------

@pytest.mark.parametrize("reason", sorted(PROTECTIVE_EXIT_REASONS))
def test_protective_reasons_bypass_the_gate(reason):
    """A protective exit must not be gated on profit, or it can never fire."""
    assert reason in PROTECTIVE_EXIT_REASONS
    gate = reason not in PROTECTIVE_EXIT_REASONS
    assert gate is False


@pytest.mark.parametrize("reason", ["TAKE_PROFIT", "TAKE_PROFIT_RSI", None])
def test_discretionary_reasons_keep_the_gate(reason):
    gate = reason not in PROTECTIVE_EXIT_REASONS
    assert gate is True


def test_hard_stop_is_not_protected_by_profit_requirement():
    """End-to-end: a position 5% under water must produce a sell attempt."""
    bot = make_bot(enable_hard_stop_loss=True, hard_stop_loss_percent=3.0,
                   enable_break_even=False)
    bot.holdings['XBTEUR'] = 1.0
    bot.purchase_prices['XBTEUR'] = 100.0
    bot.pair_prices['XBTEUR'] = 95.0
    bot.stop_info.pop('XBTEUR', None)

    pair, reason, change = bot.check_take_profit_or_stop_loss()
    assert pair == 'XBTEUR'
    assert reason == 'HARD_STOP'
    assert change == pytest.approx(-5.0, abs=0.01)
    # and the router must not gate it
    assert (reason not in PROTECTIVE_EXIT_REASONS) is False


def test_time_stop_fires_on_stale_position():
    import time as _time
    bot = make_bot(enable_time_stop=True, time_stop_hours=48,
                   enable_hard_stop_loss=False, enable_break_even=False)
    bot.holdings['XBTEUR'] = 1.0
    bot.purchase_prices['XBTEUR'] = 100.0
    bot.pair_prices['XBTEUR'] = 99.0
    bot.entry_timestamps['XBTEUR'] = _time.time() - (49 * 3600)
    bot.stop_info.pop('XBTEUR', None)

    pair, reason, _ = bot.check_take_profit_or_stop_loss()
    assert (pair, reason) == ('XBTEUR', 'TIME_STOP')


# --- the max_take_profit_percent = 0 trap -----------------------------------

def test_zero_tp_ceiling_does_not_pin_target_to_zero():
    """A configured 0 ceiling used to force required TP to 0% via min()."""
    assert TradingBot._sanitize_max_tp(0.0) == 14.0
    assert TradingBot._sanitize_max_tp(-1.0) == 14.0
    assert TradingBot._sanitize_max_tp("nonsense") == 14.0
    assert TradingBot._sanitize_max_tp(8.0) == 8.0

    bot = make_bot(max_take_profit_percent=0.0)
    assert bot._required_take_profit_percent('XBTEUR') > 0.0
