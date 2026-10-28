from dataclasses import asdict

import numpy as np
import pytest

from ledgershield.core import Rejected
from ledgershield.evidence import dataset
from ledgershield.learning import DQN, HealingEnv, RewardWeights, experiment


def test_reward_equation_and_bounded_observations():
    weights = RewardWeights()
    env = HealingEnv(horizon=4, weights=weights)
    for scenario in range(4):
        state, _ = env.reset(seed=77, options={"scenario": scenario})
        assert env.observation_space.contains(state)
        for action in (0, 1, 2, 3):
            state, reward, _, truncated, info = env.step(action)
            assert env.observation_space.contains(state)
            terms = info["reward_terms"]
            assert all(0 <= value <= 1 for value in terms.values())
            positive = {"transactions", "availability", "progress", "mitigation"}
            expected = sum(
                asdict(weights)[key] * value * (1 if key in positive else -1)
                for key, value in terms.items()
            )
            assert reward == pytest.approx(expected)
        assert truncated


def test_training_reproducible_and_eval_separated(tmp_path):
    first = experiment(episodes=2, output=tmp_path / "a", train_seed=100, eval_seed=10000)
    second = experiment(episodes=2, output=tmp_path / "b", train_seed=100, eval_seed=10000)
    assert first == second
    assert first["updates"] > 0
    assert {r["seed"] for r in first["training"]}.isdisjoint(
        {r["seed"] for r in first["evaluation"]}
    )
    assert {r["policy"] for r in first["evaluation"]} == {"no_healing", "rule", "dqn"}
    for policy in ("no_healing", "rule", "dqn"):
        assert len([r for r in first["evaluation"] if r["policy"] == policy]) == 12
    assert np.array_equal(
        DQN.load(tmp_path / "a/dqn.json").w1, DQN.load(tmp_path / "b/dqn.json").w1
    )
    with pytest.raises(Rejected, match="overlapping"):
        experiment(episodes=2, output=tmp_path / "bad", train_seed=100, eval_seed=101)


def test_synthetic_split_repeatability_and_no_duplicate_rows():
    train, _ = dataset(101)
    evaluation, _ = dataset(202)
    assert np.array_equal(train, dataset(101)[0])
    assert set(map(tuple, train)).isdisjoint(set(map(tuple, evaluation)))


@pytest.mark.parametrize("weight", [-1, float("nan"), float("inf")])
def test_invalid_reward_weights_are_rejected(weight):
    with pytest.raises(Rejected, match="invalid_reward_weights"):
        RewardWeights(latency=weight)


@pytest.mark.parametrize("horizon", [0, -1, 1001, True])
def test_invalid_episode_boundaries_are_rejected(horizon):
    with pytest.raises(Rejected, match="invalid_episode_horizon"):
        HealingEnv(horizon=horizon)
