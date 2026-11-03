# pyright: basic
# pyright: reportMissingImports=false
# torch is an optional dependency (group `train`), so strict checking is relaxed in this file.
"""AlphaZero-style self-play (2 players, zero-sum). No rule behaviour lives here.

OpenSpiel's own alpha_zero module is JAX/flax based, so this is a thin loop of our own over
`open_spiel.python.algorithms.mcts` (PUCT, root Dirichlet noise) with a net-backed Evaluator.
Chance nodes are expanded natively (`dont_return_chance_node=True`). The search clones full
game states (as the shipped MCTS bot does); the net itself only sees the mover's observation.
Value is the mover-perspective return in [-1, 1]; the evaluator reports [v, -v] by player.
"""

from __future__ import annotations

import csv
import json
import multiprocessing as mp
import random
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from open_spiel.python.algorithms import mcts
from torch import nn

from kingisdead.rl.checkpoint import load_checkpoint, save_checkpoint
from kingisdead.rl.env import NUM_ACTIONS, SelfPlayEnv, features, legal_mask
from kingisdead.rl.net import NetConfig, PolicyValueNet
from kingisdead.rl.ppo import numpy_weights

CURVE_FIELDS = [
    "iter",
    "games",
    "samples",
    "elapsed",
    "selfplay_s",
    "train_s",
    "raw_vs_random",
    "raw_vs_heuristic",
    "mcts_vs_random",
    "mcts_vs_heuristic",
    "mean_plies",
    "policy_loss",
    "value_loss",
]


@dataclass
class AZConfig:
    num_players: int = 2
    hidden_sizes: tuple[int, ...] = (256, 256)
    residual: bool = False
    workers: int = 6
    sims: int = 50
    eval_sims: int = 50
    c_puct: float = 1.5
    dirichlet_alpha: float = 0.3
    dirichlet_eps: float = 0.25
    temp_moves: int = 12  # own decisions sampled ~ visits; later moves are greedy
    games_per_iter: int = 48
    task_games: int = 2  # games per worker task (small tasks balance load)
    buffer_size: int = 200_000
    batch_size: int = 512
    sample_reuse: float = 4.0  # train steps per iter = new samples * reuse / batch_size
    min_buffer: int = 2_000
    lr: float = 1e-3
    weight_decay: float = 1e-4
    eval_every: int = 5
    eval_raw_games: int = 100
    eval_mcts_games: int = 24  # net+MCTS vs random (informational)
    eval_best_games: int = 100  # net+MCTS vs heuristic; picks best.pt (0 = use raw policy)
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["hidden_sizes"] = list(self.hidden_sizes)
        return d


def git_commit() -> str | None:
    """Best-effort current git commit hash (None if unavailable)."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=10,
        )
        h = r.stdout.strip()
        return h if r.returncode == 0 and h else None
    except Exception:
        return None


# ---------------------------------------------------------------- search


class NetEvaluator(mcts.Evaluator):
    """Net-backed MCTS evaluator. One forward per distinct state (cached within a search)."""

    def __init__(self, net: PolicyValueNet) -> None:
        self.net = net
        self._cache: dict[tuple[int, ...], tuple[list[tuple[int, float]], float]] = {}
        self.calls = 0

    def clear(self) -> None:
        self._cache.clear()

    def _eval(self, state: Any) -> tuple[list[tuple[int, float]], float]:
        key = tuple(state.history())
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        player = state.current_player()
        mask = legal_mask(state)
        x = torch.as_tensor(features(state, player)).unsqueeze(0)
        m = torch.as_tensor(mask).unsqueeze(0)
        with torch.no_grad():
            logits, value = self.net(x, m)
        legal = np.flatnonzero(mask)
        probs = torch.softmax(logits[0].double(), dim=0).numpy()[legal]
        probs = probs / probs.sum()
        res = ([(int(a), float(p)) for a, p in zip(legal, probs, strict=True)], float(value[0, 0]))
        self.calls += 1
        self._cache[key] = res
        return res

    def evaluate(self, state: Any) -> np.ndarray:
        if state.is_chance_node():
            return np.zeros(2)
        v = self._eval(state)[1]
        out = np.zeros(2)
        p = state.current_player()
        out[p], out[1 - p] = v, -v
        return out

    def prior(self, state: Any) -> list[tuple[int, float]]:
        if state.is_chance_node():
            return list(state.chance_outcomes())
        return list(self._eval(state)[0])


class NetMCTS:
    """Net-guided PUCT search agent. `search` returns (visit distribution, chosen action)."""

    def __init__(
        self,
        net: PolicyValueNet,
        sims: int,
        c_puct: float = 1.5,
        dirichlet: tuple[float, float] | None = None,
        seed: int = 0,
    ) -> None:
        self.net = net.eval()
        self.sims = sims
        self.evaluator = NetEvaluator(net)
        self.np_rng = np.random.RandomState(seed)
        game = SelfPlayEnv(2).game
        self.bot = mcts.MCTSBot(
            game,
            c_puct,
            sims,
            self.evaluator,
            solve=False,
            random_state=self.np_rng,
            child_selection_fn=mcts.SearchNode.puct_value,
            dirichlet_noise=dirichlet,
            dont_return_chance_node=True,
        )

    def search(self, state: Any) -> np.ndarray:
        """Visit-count distribution over the frozen action ids (zero on illegal actions)."""
        self.evaluator.clear()
        root = self.bot.mcts_search(state.clone())
        pi = np.zeros(NUM_ACTIONS, dtype=np.float32)
        for c in root.children:
            pi[c.action] = c.explore_count
        total = pi.sum()
        if total <= 0:
            pi[state.legal_actions()] = 1.0
            total = pi.sum()
        return pi / total

    def choose(self, state: Any, rng: random.Random) -> int:
        """Greedy (most visited) legal action; usable as a bot seat."""
        legal = state.legal_actions()
        if len(legal) == 1:
            return int(legal[0])
        self.np_rng.seed(rng.getrandbits(32))
        return int(np.argmax(self.search(state)))


def sample_from(pi: np.ndarray, rng: random.Random) -> int:
    idx = int(np.searchsorted(np.cumsum(pi), rng.random() * pi.sum(), side="right"))
    nz = np.flatnonzero(pi)
    return int(idx if pi[min(idx, pi.size - 1)] > 0 else nz[-1])


# ---------------------------------------------------------------- workers

_NET_CACHE: dict[str, Any] = {}


def _worker_net(task: dict[str, Any]) -> PolicyValueNet:
    torch.set_num_threads(1)
    key = task["version"]
    if _NET_CACHE.get("key") != key:
        net = PolicyValueNet(NetConfig.from_dict(task["net_config"]))
        net.load_state_dict({k: torch.as_tensor(v) for k, v in task["weights"].items()})
        net.eval()
        _NET_CACHE.update(key=key, net=net)
    return _NET_CACHE["net"]


def self_play_game(
    env: SelfPlayEnv, agent: NetMCTS, cfg: AZConfig, seed: int
) -> tuple[list[tuple[np.ndarray, np.ndarray, np.ndarray, float]], int]:
    """One self-play game. Returns ([(features, mask, visit pi, outcome for mover)], plies).

    Forced moves (single legal action) are played without search and not recorded.
    """
    rng = random.Random(seed ^ 0xA2)
    agent.np_rng.seed(rng.getrandbits(32))
    env.reset(seed)
    recs: list[tuple[np.ndarray, np.ndarray, np.ndarray, int]] = []
    own = [0] * env.num_players
    plies = 0
    while not env.done:
        legal = env.state.legal_actions()
        plies += 1
        if len(legal) == 1:
            env.step(int(legal[0]))
            continue
        p = env.current_player
        pi = agent.search(env.state)
        recs.append((env.features(), env.mask(), pi, p))
        a = sample_from(pi, rng) if own[p] < cfg.temp_moves else int(np.argmax(pi))
        own[p] += 1
        env.step(a)
    ret = env.returns()
    return [(f, m, pi, float(ret[p])) for f, m, pi, p in recs], plies


def selfplay_task(task: dict[str, Any]) -> dict[str, Any]:
    cfg = AZConfig(**{**task["cfg"], "hidden_sizes": tuple(task["cfg"]["hidden_sizes"])})
    net = _worker_net(task)
    env = SelfPlayEnv(cfg.num_players)
    agent = NetMCTS(net, cfg.sims, cfg.c_puct, (cfg.dirichlet_eps, cfg.dirichlet_alpha))
    obs, mask, pol, val = [], [], [], []
    plies = 0
    t0 = time.perf_counter()
    for seed in task["seeds"]:
        recs, n = self_play_game(env, agent, cfg, seed)
        plies += n
        for f, m, pi, v in recs:
            obs.append(f)
            mask.append(m)
            pol.append(pi)
            val.append(v)
    return {
        "obs": np.stack(obs) if obs else np.zeros((0, env.feature_size), np.float32),
        "mask": np.stack(mask) if mask else np.zeros((0, NUM_ACTIONS), np.bool_),
        "pi": np.stack(pol) if pol else np.zeros((0, NUM_ACTIONS), np.float32),
        "value": np.array(val, dtype=np.float32),
        "games": len(task["seeds"]),
        "plies": plies,
        "secs": time.perf_counter() - t0,
    }


def evaluate_task(task: dict[str, Any]) -> dict[str, float]:
    """Worker entry: net (mode 'raw' greedy policy, or 'mcts') vs a bot; wins (ties shared)."""
    from server.bots import get_bot

    net = _worker_net(task)
    n = 2
    env = SelfPlayEnv(n)
    bot = get_bot(task["opponent"])
    agent = NetMCTS(net, task["sims"]) if task["mode"] == "mcts" else None
    wins = 0.0
    for i in range(task["start"], task["start"] + task["games"]):
        seat = i % n
        rng = random.Random(f"{task['seed']}:eval:{i}")
        env.reset(rng.getrandbits(62))
        while not env.done:
            if env.current_player == seat:
                if agent is not None:
                    a = agent.choose(env.state, rng)
                else:
                    a = net.act(env.features(), env.mask(), greedy=True)
            else:
                a = bot.choose(env.state, rng)
            env.step(a)
        r = env.returns()
        top = max(r)
        winners = [s for s in range(n) if r[s] == top]
        if seat in winners:
            wins += 1 / len(winners)
    return {"wins": wins, "games": float(task["games"])}


# ---------------------------------------------------------------- learner


class ReplayBuffer:
    def __init__(self, capacity: int, feature_size: int) -> None:
        self.cap = capacity
        self.obs = np.zeros((capacity, feature_size), np.float32)
        self.mask = np.zeros((capacity, NUM_ACTIONS), np.bool_)
        self.pi = np.zeros((capacity, NUM_ACTIONS), np.float32)
        self.value = np.zeros(capacity, np.float32)
        self.size = 0
        self.pos = 0

    def add(self, obs: np.ndarray, mask: np.ndarray, pi: np.ndarray, value: np.ndarray) -> None:
        for i in range(len(value)):
            self.obs[self.pos], self.mask[self.pos] = obs[i], mask[i]
            self.pi[self.pos], self.value[self.pos] = pi[i], value[i]
            self.pos = (self.pos + 1) % self.cap
            self.size = min(self.size + 1, self.cap)

    def sample(self, n: int, rng: np.random.Generator) -> tuple[np.ndarray, ...]:
        idx = rng.integers(0, self.size, size=n)
        return self.obs[idx], self.mask[idx], self.pi[idx], self.value[idx]


def az_loss(
    net: PolicyValueNet,
    obs: torch.Tensor,
    mask: torch.Tensor,
    pi: torch.Tensor,
    value: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """(policy cross-entropy to the visit distribution, value MSE)."""
    logits, v = net(obs, mask)
    logp = torch.log_softmax(logits, dim=-1).masked_fill(~mask, 0.0)
    pl = -(pi * logp).sum(-1).mean()
    vl = ((v.squeeze(1) - value) ** 2).mean()
    return pl, vl


def train_steps(
    net: PolicyValueNet,
    opt: torch.optim.Optimizer,
    buf: ReplayBuffer,
    steps: int,
    batch: int,
    rng: np.random.Generator,
    device: torch.device,
) -> tuple[float, float]:
    net.train()
    pls = vls = 0.0
    for _ in range(steps):
        o, m, p, v = (torch.as_tensor(a).to(device) for a in buf.sample(batch, rng))
        pl, vl = az_loss(net, o, m, p, v)
        opt.zero_grad()
        (pl + vl).backward()
        nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        pls += pl.item()
        vls += vl.item()
    net.eval()
    return pls / max(steps, 1), vls / max(steps, 1)


def evaluate(
    mapper: Callable,
    base: dict[str, Any],
    workers: int,
    mode: str,
    opponent: str,
    games: int,
    sims: int,
    seed: int,
) -> float:
    chunks = max(1, min(workers, games))
    per = [games // chunks + (1 if i < games % chunks else 0) for i in range(chunks)]
    tasks = [
        {
            **base,
            "mode": mode,
            "opponent": opponent,
            "sims": sims,
            "start": sum(per[:i]),
            "games": per[i],
            "seed": seed,
        }
        for i in range(chunks)
    ]
    res = mapper(evaluate_task, tasks)
    return sum(r["wins"] for r in res) / max(1.0, sum(r["games"] for r in res))


def train(
    cfg: AZConfig,
    out: Path,
    minutes: float,
    max_iters: int | None = None,
    resume: bool = False,
    log: Callable[[str], None] = print,
    run_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Time-boxed AlphaZero training. Returns a summary dict."""
    if cfg.num_players != 2:
        raise ValueError("AlphaZero trainer supports 2 players only")
    out.mkdir(parents=True, exist_ok=True)
    random.seed(cfg.seed)
    torch.manual_seed(cfg.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    env = SelfPlayEnv(cfg.num_players)
    net_cfg = NetConfig(
        input_dim=env.feature_size,
        num_actions=NUM_ACTIONS,
        hidden_sizes=cfg.hidden_sizes,
        num_players=cfg.num_players,
        residual=cfg.residual,
    )
    net = PolicyValueNet(net_cfg)
    it = games_total = samples_total = 0
    elapsed_before = 0.0
    best = -1.0
    state_path = out / "state.json"
    opt_state = None
    if resume and state_path.exists():
        net, net_cfg, _ = load_checkpoint(out / "latest.pt")
        st = json.loads(state_path.read_text())
        it, games_total, samples_total = st["iter"], st["games"], st["samples"]
        elapsed_before, best = st["elapsed"], st["best"]
        if (out / "optim.pt").exists():
            opt_state = torch.load(out / "optim.pt", map_location="cpu", weights_only=True)
        log(f"resumed at iter {it}, {games_total} games (replay buffer starts empty)")
    net.to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    if opt_state is not None:
        opt.load_state_dict(opt_state)
    cpu_net = PolicyValueNet(net_cfg)
    buf = ReplayBuffer(cfg.buffer_size, env.feature_size)

    curve_path = out / "curve.csv"
    new_curve = not (resume and curve_path.exists())
    curve_f = open(curve_path, "w" if new_curve else "a", newline="")  # noqa: SIM115
    writer = csv.DictWriter(curve_f, fieldnames=CURVE_FIELDS)
    if new_curve:
        writer.writeheader()

    pool = mp.get_context("spawn").Pool(cfg.workers) if cfg.workers > 1 else None

    def mapper(fn, tasks):
        return pool.map(fn, tasks) if pool else [fn(t) for t in tasks]

    rng = random.Random(cfg.seed * 7919 + it)
    nrng = np.random.default_rng(cfg.seed + it)
    t0 = time.perf_counter()
    last_eval: dict[str, float] = {}
    meta_base = {
        "algorithm": "alphazero",
        "seed": cfg.seed,
        "train_config": cfg.to_dict(),
        "git_commit": git_commit(),
        "run_config": {
            "minutes": minutes,
            "max_iters": max_iters,
            "resume": resume,
            **(run_config or {}),
        },
    }

    def elapsed() -> float:
        return elapsed_before + time.perf_counter() - t0

    def sync_cpu() -> None:
        cpu_net.load_state_dict({k: v.detach().cpu() for k, v in net.state_dict().items()})

    def write_state() -> None:
        state_path.write_text(
            json.dumps(
                {
                    "iter": it,
                    "games": games_total,
                    "samples": samples_total,
                    "elapsed": elapsed(),
                    "best": best,
                }
            )
        )
        torch.save(opt.state_dict(), out / "optim.pt")

    sp_secs = 0.0
    sp_plies = 0
    try:
        while elapsed() - elapsed_before < minutes * 60 and (max_iters is None or it < max_iters):
            sync_cpu()
            base = {
                "version": f"{it}:{rng.random()}",
                "net_config": net_cfg.to_dict(),
                "weights": numpy_weights(cpu_net),
            }
            seeds = [rng.getrandbits(62) for _ in range(cfg.games_per_iter)]
            tasks = [
                {**base, "cfg": cfg.to_dict(), "seeds": seeds[i : i + cfg.task_games]}
                for i in range(0, len(seeds), cfg.task_games)
            ]
            ts = time.perf_counter()
            results = pool.map(selfplay_task, tasks, chunksize=1) if pool else None
            if results is None:
                results = [selfplay_task(t) for t in tasks]
            sp_s = time.perf_counter() - ts
            new = 0
            plies = 0
            for r in results:
                buf.add(r["obs"], r["mask"], r["pi"], r["value"])
                new += len(r["value"])
                plies += r["plies"]
            games_total += cfg.games_per_iter
            samples_total += new
            sp_secs += sp_s
            sp_plies += plies
            ts = time.perf_counter()
            pl = vl = float("nan")
            if buf.size >= min(cfg.min_buffer, cfg.buffer_size):
                steps = max(1, int(new * cfg.sample_reuse / cfg.batch_size))
                pl, vl = train_steps(net, opt, buf, steps, cfg.batch_size, nrng, device)
            train_s = time.perf_counter() - ts
            it += 1
            row: dict[str, Any] = {
                "iter": it,
                "games": games_total,
                "samples": samples_total,
                "elapsed": round(elapsed(), 1),
                "selfplay_s": round(sp_s, 1),
                "train_s": round(train_s, 1),
                "mean_plies": round(plies / cfg.games_per_iter, 1),
                "policy_loss": round(pl, 4),
                "value_loss": round(vl, 4),
            }
            sync_cpu()
            do_eval = cfg.eval_every > 0 and it % cfg.eval_every == 0
            if do_eval:
                eb = {
                    "version": f"eval:{it}:{rng.random()}",
                    "net_config": net_cfg.to_dict(),
                    "weights": numpy_weights(cpu_net),
                }
                s = cfg.seed
                res = {
                    "raw_vs_random": evaluate(
                        mapper, eb, cfg.workers, "raw", "random", cfg.eval_raw_games, 0, s + 1
                    ),
                    "raw_vs_heuristic": evaluate(
                        mapper, eb, cfg.workers, "raw", "heuristic", cfg.eval_raw_games, 0, s + 2
                    ),
                }
                for opp, games, sd in (
                    ("random", cfg.eval_mcts_games, s + 3),
                    ("heuristic", cfg.eval_best_games, s + 4),
                ):
                    if games > 0:
                        res[f"mcts_vs_{opp}"] = evaluate(
                            mapper, eb, cfg.workers, "mcts", opp, games, cfg.eval_sims, sd
                        )
                row.update({k: round(v, 3) for k, v in res.items()})
                last_eval = res
                crit = res.get("mcts_vs_heuristic", res["raw_vs_heuristic"])
                if crit > best:
                    best = crit
                    meta = {**meta_base, "eval_stats": {**last_eval, "iter": it}}
                    save_checkpoint(out / "best.pt", cpu_net, net_cfg, meta)
            writer.writerow(row)
            curve_f.flush()
            log(
                f"iter {it} games {games_total} t={elapsed():.0f}s "
                f"sp={sp_s:.0f}s tr={train_s:.0f}s "
                f"pl={row['policy_loss']} vl={row['value_loss']}"
                + (
                    " " + " ".join(f"{k}={row[k]}" for k in last_eval if k in row)
                    if do_eval
                    else ""
                )
            )
            save_checkpoint(
                out / "latest.pt",
                cpu_net,
                net_cfg,
                {**meta_base, "eval_stats": {**last_eval, "iter": it, "games": games_total}},
            )
            write_state()
    finally:
        curve_f.close()
        if pool:
            pool.close()
            pool.join()
    total = elapsed()
    return {
        "iters": it,
        "games": games_total,
        "samples": samples_total,
        "elapsed": total,
        "games_per_sec": games_total / max(total, 1e-9),
        "selfplay_games_per_sec": cfg.games_per_iter * it / max(sp_secs, 1e-9),
        "selfplay_moves_per_sec": sp_plies / max(sp_secs, 1e-9),
        "best": best,
        "device": str(device),
    }
