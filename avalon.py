#! /usr/bin/python3

import abc
import random
import enum
import collections
import asyncio
from typing import Dict, List, Tuple


class AvalonPlayer:
    pass


class _Side(enum.Enum):
    GOOD = 1
    EVIL = 2


_Role = collections.namedtuple("_Role", ["key", "name", "side", "know"])


class Role(enum.Enum):
    Minion = _Role(
        key="Minion",
        name="Minion of Mordred",
        side=_Side.EVIL,
        know=("Minion", "Mordred", "Morgana", "Assassin"),
    )
    Servant = _Role(
        key="Servant",
        name="Servant of Arthur",
        side=_Side.GOOD,
        know=(),
    )
    Merlin = _Role(
        key="Merlin",
        name="Merlin",
        side=_Side.GOOD,
        know=("Minion", "Morgana", "Assassin", "Oberon"),
    )
    Mordred = _Role(
        key="Mordred",
        name="Mordred",
        side=_Side.EVIL,
        know=("Minion", "Mordred", "Morgana", "Assassin"),
    )
    Morgana = _Role(
        key="Morgana",
        name="Morgana",
        side=_Side.EVIL,
        know=("Minion", "Mordred", "Morgana", "Assassin"),
    )
    Percival = _Role(
        key="Percival",
        name="Percival",
        side=_Side.GOOD,
        know=("Merlin", "Morgana"),
    )
    Assassin = _Role(
        key="Assassin",
        name="Assassin",
        side=_Side.EVIL,
        know=("Minion", "Mordred", "Morgana", "Assassin"),
    )
    Oberon = _Role(
        key="Oberon",
        name="Oberon",
        side=_Side.EVIL,
        know=(),
    )


class Player(abc.ABC):
    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    async def send(self, msg: str) -> None: ...

    @abc.abstractmethod
    async def input(self, kind: str) -> str: ...


_Rules = collections.namedtuple("_Rules", ["total_evil"])
_rules = {
    5: _Rules(2),
    6: _Rules(2),
    7: _Rules(3),
    8: _Rules(3),
    9: _Rules(3),
    10: _Rules(4),
}


class Game:
    def __init__(self, players: List[Player], roles: List[Role]):
        self.players = players
        self.roles = roles
        active_rules = _rules[len(players)]
        evils = active_rules.total_evil
        goods = len(players) - evils
        evil_roles = [r for r in roles if r.value.side == _Side.EVIL]
        good_roles = [r for r in roles if r.value.side == _Side.GOOD]
        if len(evil_roles) > evils:
            raise ValueError("Too many evil roles")
        if len(good_roles) > goods:
            raise ValueError("Too many good roles")
        evil_roles.extend([Role.Minion] * (evils - len(evil_roles)))
        good_roles.extend([Role.Servant] * (goods - len(good_roles)))
        all_roles = evil_roles + good_roles
        random.shuffle(all_roles)
        self.player_map = list(zip(players, all_roles))

    async def broadcast(self, msg: str) -> None:
        await asyncio.gather(*[player.send(msg) for player in self.players])

    async def vote(self) -> Dict[str, str]:
        results = await asyncio.gather(
            *[player.input("vote") for player in self.players]
        )
        return {player.name: result for player, result in zip(self.players, results)}

    async def send_initial_info(self, idx: int) -> None:
        player, role = self.player_map[idx]
        await player.send(f"Welcome to Avalon, {player.name}!")
        await player.send(f"Your role is {role.value.name}")
        know = []
        for other_player, other_role in self.player_map:
            if other_player is player:
                continue
            if other_role.value.key in role.value.know:
                know.append(other_player.name)
        if know:
            await player.send("Here are the players you should know about:")
            await player.send(" ".join(know))

    async def play(self) -> None:
        await asyncio.gather(
            *[self.send_initial_info(idx) for idx in range(len(self.player_map))]
        )
