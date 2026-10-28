"""Small NumPy DQN with replay and a target network; training is explicit/offline."""
from collections import deque
from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from .core import Rejected, digest
from .network import Network, NetworkConfig
from .evidence import TrustEngine
from .recovery import ACTIONS, Orchestrator, RecoveryConfig


@dataclass
class RewardWeights:
    transactions: float = 1.0
    availability: float = .3
    progress: float = .5
    latency: float = .2
    mitigation: float = .5
    false_positive: float = 1.0
    intervention: float = .05
    collateral: float = .5
    recovery_duration: float = .1


class HealingEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, horizon=20, weights=None):
        self.action_space = spaces.Discrete(len(ACTIONS))
        self.observation_space = spaces.Box(0, 1, (12,), dtype=np.float32)
        self.horizon, self.weights = horizon, weights or RewardWeights()
        self.net = None
        self.last_action = 0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.net = Network(NetworkConfig(seed=int(self.np_random.integers(0, 2**30))))
        scenario = (options or {}).get("scenario", int(self.np_random.integers(0, 4)))
        self.scenario = int(scenario)
        if self.scenario not in range(4):
            raise Rejected("invalid_scenario")
        self.target = "node_1"
        self.net.nodes[self.target].behavior = ("honest", "unavailable", "malicious", "faulty")[self.scenario]
        self.trust = TrustEngine()
        self.recovery = Orchestrator(self.net, self.trust, RecoveryConfig(mode="autonomous_simulation"))
        self.steps, self.last_action = 0, 0
        self.net.round()  # Observable evidence before choosing a response.
        return self.observation(), self.info()

    def observation(self):
        m = self.net.summary()
        node = self.net.nodes[self.target]
        stats = self.net.node_metrics[self.target]
        return np.clip(np.array([
            m["availability"], self.trust.get(self.target) / 100,
            m["accepted"] / max(1, m["submitted"]), float(self.net.last_round["committed"]),
            m["message_latency_ms"] / self.net.config.timeout_ms,
            stats["timeouts"] / max(1, stats["attempts"]),
            stats["invalid_votes"] / max(1, stats["invalid_votes"] + stats["votes"]),
            float(node.quarantined), float(node.monitoring), self.last_action / 6,
            self.steps / self.horizon, m["stalls"] / max(1, self.net.tick)
        ], dtype=np.float32), 0, 1)

    def info(self):
        audit = self.recovery.audit
        recovered = sum(r["status"] == "recovered" for r in audit)
        metrics = {**self.net.summary(), "anomalies": 0, "trust_changes": len(self.trust.audit),
                   "recovery_attempts": sum("attempt" in r for r in audit),
                   "recovery_successes": recovered,
                   "recovery_failures": sum(r["status"] == "rolled_back" for r in audit)}
        return {"metrics": metrics, "scenario": self.scenario, "recoveries": recovered}

    def step(self, action):
        if not self.action_space.contains(action):
            raise Rejected("invalid_action")
        action = int(action)
        self.steps += 1
        before = self.net.summary()
        target = self.net.nodes[self.target]
        honest = target.behavior == "honest"
        verified = self.net.node_metrics[self.target]["invalid_votes"] > 0
        evidence = {"verified": verified, "method": "episode_telemetry"}
        record = self.recovery.propose(self.target, ACTIONS[action], evidence,
                                       digest([self.steps, action, self.net.config.seed]))
        self.net.demo_transaction()
        committed = self.net.round()
        after = self.net.summary()
        w = self.weights
        terms = {
            "transactions": float(after["committed_transactions"] > before["committed_transactions"]),
            "availability": after["availability"], "progress": float(committed),
            "latency": min(1, after["message_latency_ms"] / self.net.config.timeout_ms),
            "mitigation": float(record["status"] == "recovered" and not honest),
            "false_positive": float(honest and action in (2, 3, 4, 6)),
            "intervention": float(action != 0),
            "collateral": min(1, len(record.get("collateral_nodes", [])) / len(self.net.nodes)),
            "recovery_duration": min(1, record.get("duration_ticks", 0) / self.recovery.config.timeout_ticks)}
        positive = ("transactions", "availability", "progress", "mitigation")
        reward = sum(getattr(w, k) * v * (1 if k in positive else -1) for k, v in terms.items())
        self.last_action = action
        return self.observation(), reward, False, self.steps >= self.horizon, {
            **self.info(), "reward_terms": terms, "recovery": record["status"]}


def baseline_action(obs):
    if obs[6] > .2 and obs[7] == 0:
        return 2
    if obs[5] > .5:
        return 3
    return 0


class DQN:
    def __init__(self, seed=42, hidden=32):
        self.rng = np.random.default_rng(seed)
        self.w1 = self.rng.normal(0, .15, (12, hidden))
        self.b1 = np.zeros(hidden)
        self.w2 = self.rng.normal(0, .15, (hidden, len(ACTIONS)))
        self.b2 = np.zeros(len(ACTIONS))
        self.target = self.params()
        self.replay = deque(maxlen=5000)
        self.updates = 0

    def params(self):
        return [a.copy() for a in (self.w1, self.b1, self.w2, self.b2)]

    def predict(self, obs):
        return np.maximum(0, obs @ self.w1 + self.b1) @ self.w2 + self.b2

    def act(self, obs, epsilon=0):
        if self.rng.random() < epsilon:
            return int(self.rng.integers(len(ACTIONS)))
        q = self.predict(obs)
        if q.shape != (len(ACTIONS),) or not np.isfinite(q).all():
            return baseline_action(obs)
        return int(q.argmax())

    def learn(self, transition, batch=32, lr=.002, gamma=.95):
        self.replay.append(transition)
        if len(self.replay) < batch:
            return None
        rows = [self.replay[i] for i in self.rng.choice(len(self.replay), batch, replace=False)]
        s, a, r, ns, done = map(np.array, zip(*rows))
        tw1, tb1, tw2, tb2 = self.target
        target = r + gamma * (1 - done) * (np.maximum(0, ns @ tw1 + tb1) @ tw2 + tb2).max(axis=1)
        hidden = np.maximum(0, s @ self.w1 + self.b1)
        q = hidden @ self.w2 + self.b2
        err = np.clip(q[np.arange(batch), a] - target, -5, 5)
        grad = np.zeros_like(q)
        grad[np.arange(batch), a] = 2 * err / batch
        dh = (grad @ self.w2.T) * (hidden > 0)
        self.w2 -= lr * hidden.T @ grad
        self.b2 -= lr * grad.sum(axis=0)
        self.w1 -= lr * s.T @ dh
        self.b1 -= lr * dh.sum(axis=0)
        self.updates += 1
        if self.updates % 50 == 0:
            self.target = self.params()
        return float(np.mean(err**2))

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({"version": 1, "actions": ACTIONS,
                                        "updates": self.updates,
                                        "params": [p.tolist() for p in self.params()]}))

    @classmethod
    def load(cls, path):
        obj = json.loads(Path(path).read_text())
        if obj["version"] != 1 or obj["actions"] != list(ACTIONS):
            raise Rejected("incompatible_model")
        params = [np.array(p, dtype=float) for p in obj["params"]]
        model = cls(hidden=len(params[1]))
        if any(a.shape != b.shape or not np.isfinite(a).all() for a, b in zip(params, model.params())) or len(params) != 4:
            raise Rejected("invalid_model")
        model.w1, model.b1, model.w2, model.b2 = params
        model.updates = obj["updates"]
        model.target = model.params()
        return model


def load_policy(path):
    try:
        return DQN.load(path).act, "dqn"
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return baseline_action, "rule_fallback"


def experiment(episodes=40, output="artifacts", train_seed=100, eval_seed=10000):
    if episodes < 1 or not (train_seed + episodes <= eval_seed or eval_seed + 12 <= train_seed):
        raise Rejected("overlapping_or_invalid_experiment_seeds")
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    model, env = DQN(train_seed), HealingEnv()
    history = []
    for ep in range(episodes):
        obs, _ = env.reset(seed=train_seed + ep, options={"scenario": ep % 4})
        total, losses = 0, []
        for _ in range(env.horizon):
            action = model.act(obs, epsilon=max(.05, 1 - ep / episodes))
            nxt, reward, term, trunc, info = env.step(action)
            loss = model.learn((obs, action, reward, nxt, term or trunc))
            if loss is not None:
                losses.append(loss)
            obs, total = nxt, total + reward
        history.append({"episode": ep, "seed": train_seed + ep, "reward": total,
                        "loss": float(np.mean(losses)) if losses else None, **info["metrics"]})
    checkpoint = out / "dqn.json"
    model.save(checkpoint)
    loaded = DQN.load(checkpoint)
    evaluations = []
    for name, policy in (("no_healing", lambda _: 0), ("rule", baseline_action), ("dqn", loaded.act)):
        for ep in range(12):
            obs, _ = env.reset(seed=eval_seed + ep, options={"scenario": ep % 4})
            total = 0
            for _ in range(env.horizon):
                obs, reward, _, _, info = env.step(policy(obs))
                total += reward
            evaluations.append({"policy": name, "seed": eval_seed + ep, "scenario": ep % 4,
                                "reward": total, "recoveries": info["recoveries"], **info["metrics"]})
    report = {"training": history, "evaluation": evaluations, "updates": model.updates,
              "weights": asdict(env.weights), "train_seed": train_seed, "eval_seed": eval_seed,
              "claim": "Measured toy-simulator results only; no guarantee of improvement or generalization."}
    (out / "experiment.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=40)
    parser.add_argument("--output", default="artifacts")
    args = parser.parse_args()
    report = experiment(args.episodes, args.output)
    print(json.dumps({"updates": report["updates"], "evaluation_episodes": len(report["evaluation"])}))
