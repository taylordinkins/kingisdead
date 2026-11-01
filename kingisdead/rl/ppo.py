# pyright: basic
# torch is an optional dependency (group `train`), so strict checking is relaxed in this file.
"""Self-play PPO with action masking (2 players, zero-sum). No rule behaviour lives here.

Value target: the final return (in [-1, 1]) of the seat that moved; reward only at terminal,
gamma = 1, so the GAE target is the (lambda-mixed) final return. Rollouts run in CPU worker
processes (spawned); the learner runs on GPU if available.
"""

from __future__ import annotations

import csv
import json
import multiprocessing as mp
import random
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from kingisdead.rl.checkpoint import load_checkpoint, save_checkpoint
from kingisdead.rl.env import NUM_ACTIONS, SelfPlayEnv
from kingisdead.rl.net import NetConfig, PolicyValueNet

CURVE_FIELDS = [
    "update",
    "games",
    "elapsed",
    "winrate_vs_random",
    "winrate_vs_heuristic",
    "mean_plies",
    "policy_loss",
    "value_loss",
    "entropy",
]


@dataclass
class PPOConfig:
    num_players: int = 2
    hidden_sizes: tuple[int, ...] = (256, 256)
    residual: bool = False
    workers: int = 6
    games_per_update: int = 96
    epochs: int = 4
    minibatch: int = 1024
    lr: float = 3e-4
    gamma: float = 1.0
    lam: float = 0.95
    clip: float = 0.2
    vf_coef: float = 0.5
    ent_coef: float = 0.01
    max_grad_norm: float = 0.5
    opponent_frac: float = 0.2  # share of games vs snapshots/heuristic/random
    snapshot_every: int = 10
    max_snapshots: int = 8
    eval_every: int = 10
    eval_games: int = 100
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["hidden_sizes"] = list(self.hidden_sizes)
        return d


@dataclass
class Batch:
    obs: np.ndarray
    mask: np.ndarray
    act: np.ndarray
    logp: np.ndarray
    adv: np.ndarray
    ret: np.ndarray
    games: int = 0
    plies: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def gae(
    rewards: np.ndarray, values: np.ndarray, gamma: float, lam: float
) -> tuple[np.ndarray, np.ndarray]:
    """GAE over one finished trajectory (bootstrap value 0 after the last step).

    Returns (advantages, value targets = advantages + values).
    """
    n = len(rewards)
    adv = np.zeros(n, dtype=np.float32)
    last = 0.0
    for t in range(n - 1, -1, -1):
        next_v = values[t + 1] if t + 1 < n else 0.0
        delta = rewards[t] + gamma * next_v - values[t]
        last = delta + gamma * lam * last
        adv[t] = last
    return adv, adv + values.astype(np.float32)


# ---------------------------------------------------------------- worker side


def _build_net(config_dict: dict[str, Any], weights: dict[str, np.ndarray]) -> PolicyValueNet:
    net = PolicyValueNet(NetConfig.from_dict(config_dict))
    net.load_state_dict({k: torch.as_tensor(v) for k, v in weights.items()})
    net.eval()
    return net


def numpy_weights(net: nn.Module) -> dict[str, np.ndarray]:
    return {k: v.detach().cpu().numpy().copy() for k, v in net.state_dict().items()}


class _Seat:
    """One seat's policy: a net (sampled or greedy, optionally recorded) or a bot."""

    def __init__(
        self, net: Any = None, bot: Any = None, greedy: bool = False, record: bool = False
    ):
        self.net, self.bot, self.greedy, self.record = net, bot, greedy, record
        self.steps: list[tuple[np.ndarray, np.ndarray, int, float, float]] = []


def _choose(seat: _Seat, env: SelfPlayEnv, rng: random.Random) -> int:
    mask = env.mask()
    legal = np.flatnonzero(mask)
    if seat.bot is not None:
        return int(seat.bot.choose(env.state, rng))
    if legal.size == 1:
        return int(legal[0])
    obs = env.features()
    with torch.no_grad():
        logits, value = seat.net(
            torch.as_tensor(obs).unsqueeze(0), torch.as_tensor(mask).unsqueeze(0)
        )
    logits = logits[0]
    if seat.greedy:
        return int(torch.argmax(logits).item())
    logp_all = torch.log_softmax(logits.double(), dim=0)
    probs = logp_all.exp().numpy()[legal]
    probs = probs / probs.sum()
    idx = int(np.searchsorted(np.cumsum(probs), rng.random(), side="right"))
    a = int(legal[min(idx, legal.size - 1)])
    if seat.record:
        seat.steps.append((obs, mask, a, float(logp_all[a].item()), float(value[0, 0].item())))
    return a


def play_game(env: SelfPlayEnv, seats: list[_Seat], seed: int) -> list[float]:
    rng = random.Random(seed ^ 0x5EED)
    env.reset(seed)
    while not env.done:
        a = _choose(seats[env.current_player], env, rng)
        env.step(a)
    return env.returns()


def _bot(name: str):
    from server.bots import get_bot

    return get_bot(name)


def collect(task: dict[str, Any]) -> Batch:
    """Worker entry: play task['games'] games and return GAE-processed learner steps."""
    torch.set_num_threads(1)
    cfg = task["cfg"]
    env = SelfPlayEnv(cfg["num_players"])
    learner = _build_net(task["net_config"], task["weights"])
    opp_net = None
    if task.get("opp_weights") is not None:
        opp_net = _build_net(task["net_config"], task["opp_weights"])
    base = task["seed"]
    rng = random.Random(base)
    cols: dict[str, list] = {k: [] for k in ("obs", "mask", "act", "logp", "adv", "ret")}
    plies = 0
    for g in range(task["games"]):
        kind = task["kinds"][g]
        n = cfg["num_players"]
        seats: list[_Seat] = []
        learner_seat = rng.randrange(n)
        for s in range(n):
            if kind == "self" or s == learner_seat:
                seats.append(_Seat(net=learner, record=True))
            elif kind == "snapshot":
                seats.append(_Seat(net=opp_net))
            else:
                seats.append(_Seat(bot=_bot(kind)))
        returns = play_game(env, seats, rng.getrandbits(62))
        for s, seat in enumerate(seats):
            if not seat.record or not seat.steps:
                continue
            k = len(seat.steps)
            rewards = np.zeros(k, dtype=np.float32)
            rewards[-1] = returns[s]
            values = np.array([st[4] for st in seat.steps], dtype=np.float32)
            adv, ret = gae(rewards, values, cfg["gamma"], cfg["lam"])
            cols["obs"].append(np.stack([st[0] for st in seat.steps]))
            cols["mask"].append(np.stack([st[1] for st in seat.steps]))
            cols["act"].append(np.array([st[2] for st in seat.steps], dtype=np.int64))
            cols["logp"].append(np.array([st[3] for st in seat.steps], dtype=np.float32))
            cols["adv"].append(adv)
            cols["ret"].append(ret)
            plies += k
    if cols["obs"]:
        arr = {k: np.concatenate(v) for k, v in cols.items()}
    else:
        arr = {
            "obs": np.zeros((0, env.feature_size), np.float32),
            "mask": np.zeros((0, NUM_ACTIONS), np.bool_),
            "act": np.zeros(0, np.int64),
            "logp": np.zeros(0, np.float32),
            "adv": np.zeros(0, np.float32),
            "ret": np.zeros(0, np.float32),
        }
    return Batch(
        arr["obs"],
        arr["mask"],
        arr["act"],
        arr["logp"],
        arr["adv"],
        arr["ret"],
        games=task["games"],
        plies=plies,
    )


def evaluate_task(task: dict[str, Any]) -> dict[str, float]:
    """Worker entry: greedy net vs a bot; returns wins (ties shared) and games played."""
    torch.set_num_threads(1)
    n = task["num_players"]
    env = SelfPlayEnv(n)
    net = _build_net(task["net_config"], task["weights"])
    bot = _bot(task["opponent"])
    wins = 0.0
    for i in range(task["start"], task["start"] + task["games"]):
        net_seat = i % n
        seats = [_Seat(net=net, greedy=True) if s == net_seat else _Seat(bot=bot) for s in range(n)]
        returns = play_game(env, seats, random.Random(f"{task['seed']}:eval:{i}").getrandbits(62))
        top = max(returns)
        winners = [s for s in range(n) if returns[s] == top]
        if net_seat in winners:
            wins += 1 / len(winners)
    return {"wins": wins, "games": float(task["games"])}


# ---------------------------------------------------------------- learner side


def choose_kinds(
    rng: random.Random, n: int, opponent_frac: float, have_snapshots: bool
) -> list[str]:
    kinds = []
    for _ in range(n):
        if rng.random() >= opponent_frac:
            kinds.append("self")
        else:
            options = ["heuristic", "random"] + (["snapshot"] * 2 if have_snapshots else [])
            kinds.append(rng.choice(options))
    return kinds


def ppo_update(
    net: PolicyValueNet,
    opt: torch.optim.Optimizer,
    data: dict[str, torch.Tensor],
    cfg: PPOConfig,
    rng: torch.Generator,
) -> dict[str, float]:
    n = data["obs"].shape[0]
    adv = data["adv"]
    adv = (adv - adv.mean()) / (adv.std() + 1e-8) if n > 1 else adv
    stats = {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}
    count = 0
    net.train()
    for _ in range(cfg.epochs):
        perm = torch.randperm(n, generator=rng).to(data["obs"].device)
        for i in range(0, n, cfg.minibatch):
            idx = perm[i : i + cfg.minibatch]
            logits, value = net(data["obs"][idx], data["mask"][idx])
            logp_all = torch.log_softmax(logits, dim=-1)
            logp = logp_all.gather(1, data["act"][idx].unsqueeze(1)).squeeze(1)
            ratio = torch.exp(logp - data["logp"][idx])
            a = adv[idx]
            pl = -torch.min(ratio * a, torch.clamp(ratio, 1 - cfg.clip, 1 + cfg.clip) * a).mean()
            vl = ((value.squeeze(1) - data["ret"][idx]) ** 2).mean()
            probs = logp_all.exp()
            ent = -(probs * logp_all.masked_fill(~data["mask"][idx], 0.0)).sum(-1).mean()
            loss = pl + cfg.vf_coef * vl - cfg.ent_coef * ent
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), cfg.max_grad_norm)
            opt.step()
            stats["policy_loss"] += pl.item()
            stats["value_loss"] += vl.item()
            stats["entropy"] += ent.item()
            count += 1
    net.eval()
    return {k: v / max(count, 1) for k, v in stats.items()}


def merge(batches: list[Batch]) -> Batch:
    return Batch(
        obs=np.concatenate([b.obs for b in batches]),
        mask=np.concatenate([b.mask for b in batches]),
        act=np.concatenate([b.act for b in batches]),
        logp=np.concatenate([b.logp for b in batches]),
        adv=np.concatenate([b.adv for b in batches]),
        ret=np.concatenate([b.ret for b in batches]),
        games=sum(b.games for b in batches),
        plies=sum(b.plies for b in batches),
    )


def evaluate(
    mapper: Callable, net: PolicyValueNet, cfg: PPOConfig, opponent: str, games: int, seed: int
) -> float:
    """Greedy win rate of `net` vs a bot over `games` games with seat rotation."""
    chunks = max(1, min(cfg.workers, games))
    per = [games // chunks + (1 if i < games % chunks else 0) for i in range(chunks)]
    starts = [sum(per[:i]) for i in range(chunks)]
    w = numpy_weights(net)
    tasks = [
        {
            "num_players": cfg.num_players,
            "net_config": net.config.to_dict(),
            "weights": w,
            "opponent": opponent,
            "start": starts[i],
            "games": per[i],
            "seed": seed,
        }
        for i in range(chunks)
    ]
    res = mapper(evaluate_task, tasks)
    return sum(r["wins"] for r in res) / max(1.0, sum(r["games"] for r in res))


def train(
    cfg: PPOConfig,
    out: Path,
    minutes: float,
    max_updates: int | None = None,
    resume: bool = False,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Time-boxed PPO self-play training. Returns a summary dict."""
    if cfg.num_players != 2:
        raise ValueError("PPO trainer supports 2 players only")
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
    update = games_total = 0
    elapsed_before = 0.0
    best = -1.0
    state_path = out / "state.json"
    opt_state = None
    if resume and state_path.exists():
        net, net_cfg, _ = load_checkpoint(out / "latest.pt")
        st = json.loads(state_path.read_text())
        update, games_total = st["update"], st["games"]
        elapsed_before, best = st["elapsed"], st["best_heuristic"]
        if (out / "optim.pt").exists():
            opt_state = torch.load(out / "optim.pt", map_location="cpu", weights_only=True)
        log(f"resumed at update {update}, {games_total} games")
    net.to(device)
    opt = torch.optim.Adam(net.parameters(), lr=cfg.lr)
    if opt_state is not None:
        opt.load_state_dict(opt_state)
    cpu_net = PolicyValueNet(net_cfg)

    curve_path = out / "curve.csv"
    new_curve = not (resume and curve_path.exists())
    curve_f = open(curve_path, "w" if new_curve else "a", newline="")  # noqa: SIM115
    writer = csv.DictWriter(curve_f, fieldnames=CURVE_FIELDS)
    if new_curve:
        writer.writeheader()

    ctx = mp.get_context("spawn")
    pool = ctx.Pool(cfg.workers) if cfg.workers > 1 else None

    def mapper(fn, tasks):
        return pool.map(fn, tasks) if pool else [fn(t) for t in tasks]

    snapshots: list[dict[str, np.ndarray]] = []
    rng = random.Random(cfg.seed * 7919 + update)
    trng = torch.Generator().manual_seed(cfg.seed + update)
    t0 = time.perf_counter()
    summary: dict[str, Any] = {}
    last_eval: dict[str, float] = {}
    meta_base = {"algorithm": "ppo-selfplay", "seed": cfg.seed, "train_config": cfg.to_dict()}

    def elapsed() -> float:
        return elapsed_before + time.perf_counter() - t0

    def sync_cpu() -> dict[str, np.ndarray]:
        cpu_net.load_state_dict({k: v.detach().cpu() for k, v in net.state_dict().items()})
        return numpy_weights(cpu_net)

    def write_state() -> None:
        state_path.write_text(
            json.dumps(
                {
                    "update": update,
                    "games": games_total,
                    "elapsed": elapsed(),
                    "best_heuristic": best,
                }
            )
        )
        torch.save(opt.state_dict(), out / "optim.pt")

    try:
        while elapsed() - elapsed_before < minutes * 60 and (
            max_updates is None or update < max_updates
        ):
            weights = sync_cpu()
            kinds = choose_kinds(rng, cfg.games_per_update, cfg.opponent_frac, bool(snapshots))
            w = max(1, cfg.workers)
            tasks = []
            for i in range(w):
                ks = kinds[i::w]
                if not ks:
                    continue
                tasks.append(
                    {
                        "cfg": cfg.to_dict(),
                        "net_config": net_cfg.to_dict(),
                        "weights": weights,
                        "opp_weights": rng.choice(snapshots) if snapshots else None,
                        "games": len(ks),
                        "kinds": ks,
                        "seed": rng.getrandbits(62),
                    }
                )
            batch = merge(mapper(collect, tasks))
            data = {
                "obs": torch.as_tensor(batch.obs).to(device),
                "mask": torch.as_tensor(batch.mask).to(device),
                "act": torch.as_tensor(batch.act).to(device),
                "logp": torch.as_tensor(batch.logp).to(device),
                "adv": torch.as_tensor(batch.adv).to(device),
                "ret": torch.as_tensor(batch.ret).to(device),
            }
            stats = ppo_update(net, opt, data, cfg, trng)
            update += 1
            games_total += batch.games
            if update % cfg.snapshot_every == 0:
                snapshots.append(sync_cpu())
                snapshots[:] = snapshots[-cfg.max_snapshots :]
            row = {
                "update": update,
                "games": games_total,
                "elapsed": round(elapsed(), 1),
                "winrate_vs_random": "",
                "winrate_vs_heuristic": "",
                "mean_plies": round(batch.plies / max(batch.games, 1), 1),
                **{k: round(v, 4) for k, v in stats.items()},
            }
            do_eval = cfg.eval_every > 0 and update % cfg.eval_every == 0
            if do_eval:
                cpu_net.load_state_dict({k: v.detach().cpu() for k, v in net.state_dict().items()})
                wr = evaluate(mapper, cpu_net, cfg, "random", cfg.eval_games, cfg.seed + 1)
                wh = evaluate(mapper, cpu_net, cfg, "heuristic", cfg.eval_games, cfg.seed + 2)
                row["winrate_vs_random"], row["winrate_vs_heuristic"] = round(wr, 3), round(wh, 3)
                last_eval = {"winrate_vs_random": wr, "winrate_vs_heuristic": wh}
                meta = {
                    **meta_base,
                    "eval_stats": {**last_eval, "update": update, "games": games_total},
                }
                if wh > best:
                    best = wh
                    save_checkpoint(out / "best.pt", cpu_net, net_cfg, meta)
            writer.writerow(row)
            curve_f.flush()
            log(
                f"upd {update} games {games_total} t={elapsed():.0f}s plies/g={row['mean_plies']} "
                f"ent={row['entropy']} vl={row['value_loss']}"
                + (
                    f" vsR={row['winrate_vs_random']} vsH={row['winrate_vs_heuristic']}"
                    if do_eval
                    else ""
                )
            )
            cpu_net.load_state_dict({k: v.detach().cpu() for k, v in net.state_dict().items()})
            save_checkpoint(
                out / "latest.pt",
                cpu_net,
                net_cfg,
                {**meta_base, "eval_stats": {**last_eval, "update": update, "games": games_total}},
            )
            write_state()
    finally:
        curve_f.close()
        if pool:
            pool.close()
            pool.join()
    total = elapsed()
    summary = {
        "updates": update,
        "games": games_total,
        "elapsed": total,
        "games_per_sec": games_total / max(total, 1e-9),
        "best_heuristic": best,
        "device": str(device),
    }
    return summary
