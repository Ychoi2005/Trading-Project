from dataclasses import replace

import pytest

from marketlens.config import FaultConfig, MarketConfig, OrderConfig, PolicyConfig
from marketlens.execution import TruthPath, evaluate_policy, execute_buy
from marketlens.faults import inject_faults
from marketlens.market import simulate_market
from marketlens.policies import AlwaysExecute, WaitForFreshData


def test_costs_truth_and_no_double_counting():
    path = simulate_market(MarketConfig(volatility=0, spread=0.2, liquidity=100))
    order = OrderConfig(quantity=10, fee_per_share=0.01, impact_coefficient=0.5)
    fill = execute_buy(path[0], 1000, order, 99)
    assert fill.execution_price == pytest.approx(100.15)
    assert fill.spread_cost == pytest.approx(1)
    assert fill.impact_cost == pytest.approx(0.5)
    assert fill.fees == pytest.approx(0.1)
    assert fill.implementation_shortfall == pytest.approx(11.6)
    assert fill.implementation_shortfall == pytest.approx(
        10 * (fill.mid - 99) + fill.spread_cost + fill.impact_cost + fill.fees
    )


def test_stale_quote_not_executable_at_historical_price():
    path = simulate_market(MarketConfig(volatility=0, drift=10000))
    ds = inject_faults(path, FaultConfig(latency_ms=500))
    order = OrderConfig()
    result = evaluate_policy(path, ds, AlwaysExecute(), order)
    assert result.fill.mid == TruthPath(path).at(1000).mid
    assert result.trace[0].observation.quote.mid == TruthPath(path).at(500).mid
    assert result.fill.mid != result.trace[0].observation.quote.mid


@pytest.mark.parametrize("liquidity", [0, 5])
def test_unfilled_orders_and_penalty(liquidity):
    path = simulate_market(MarketConfig(liquidity=liquidity, volatility=0))
    order = OrderConfig(quantity=10)
    result = evaluate_policy(path, (), AlwaysExecute(), order)
    assert result.fill is None
    assert result.execution_delay_ms is None
    assert result.penalized_cost(0.1, 10) == 1
    assert result.reason == "Insufficient ask liquidity"


def test_horizon_before_timeout_and_inclusive_deadline():
    path = simulate_market(MarketConfig(duration_ms=1200))
    result = evaluate_policy(path, (), WaitForFreshData(), OrderConfig())
    assert result.end_time_ms == 1200
    assert result.reason == "Simulation horizon reached"
    ds = inject_faults(path, FaultConfig(latency_ms=1200))
    result = evaluate_policy(
        path,
        ds,
        WaitForFreshData(PolicyConfig(freshness_ms=2000)),
        OrderConfig(arrival_ms=1000, deadline_ms=1200),
    )
    assert result.fill.time_ms == 1200


def test_piecewise_constant_and_path_validation():
    path = simulate_market(MarketConfig())
    assert TruthPath(path).at(49) == path[0]
    with pytest.raises(ValueError):
        TruthPath(())
    with pytest.raises(ValueError):
        TruthPath(tuple(reversed(path)))
    with pytest.raises(ValueError):
        TruthPath(path).at(10001)
    with pytest.raises(ValueError):
        evaluate_policy(path, (), AlwaysExecute(), OrderConfig(arrival_ms=20000, deadline_ms=21000))
    with pytest.raises(ValueError):
        evaluate_policy(path, (), AlwaysExecute(), OrderConfig(), decision_step_ms=0)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(quantity=0),
        dict(fee_per_share=-1),
        dict(impact_coefficient=float("inf")),
        dict(deadline_ms=0),
        dict(benchmark_price=0),
    ],
)
def test_invalid_order(kwargs):
    with pytest.raises(ValueError):
        OrderConfig(**kwargs)


def test_counterfactual_nonexecution_cost_uses_common_endpoint():
    path = simulate_market(MarketConfig(volatility=0, drift=1000))
    order = OrderConfig()
    result = evaluate_policy(path, (), WaitForFreshData(), order)
    expected = (TruthPath(path).at(order.deadline_ms).mid - TruthPath(path).at(1000).mid) * 100
    assert result.opportunity_cost == pytest.approx(expected)
    assert result.penalized_cost(0, 100) == pytest.approx(expected)
    assert result.penalized_cost(1, 100) == pytest.approx(expected + 100)


def test_execution_rejects_future_state_and_invalid_times():
    path = simulate_market(MarketConfig())
    order = OrderConfig()
    with pytest.raises(ValueError, match="future"):
        execute_buy(path[-1], 1000, order, 100)
    with pytest.raises(ValueError, match="arrival"):
        execute_buy(path[0], 500, order, 100)
    with pytest.raises(ValueError):
        TruthPath(path).at(0.5)


def test_execution_rejects_numeric_overflow():
    state = replace(simulate_market(MarketConfig())[0], ask_liquidity=1e308)
    with pytest.raises(ValueError, match="numeric"):
        execute_buy(state, 1000, OrderConfig(quantity=1e308, impact_coefficient=1e308), 100)
