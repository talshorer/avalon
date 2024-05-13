#! /usr/bin/python3

from __future__ import annotations

import abc
import asyncio
import collections
import dataclasses
import enum
import itertools
import random
from typing import Dict, List, Optional, Tuple


def quest_goes(go: bool) -> str:
    return "This quest will {}go forward".format("" if go else "not ")


def going_on_a_quest(knight_names: str) -> str:
    return f"{knight_names} are going on a quest!"


class _Side(enum.Enum):
    GOOD = "Good"
    EVIL = "Evil"


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


def your_role(role: Role) -> str:
    return f"Your role is {role.value.name}"


class Player(abc.ABC):
    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    async def send(self, msg: str) -> None: ...

    @abc.abstractmethod
    async def input_players(self, msg: str, count: int) -> List[str]: ...

    @abc.abstractmethod
    async def input_vote(self, msg: str) -> bool: ...


@dataclasses.dataclass
class Quest:
    num_players: int
    required_fails: int


@dataclasses.dataclass
class Rules:
    total_evil: int
    quests: List[Quest]


_default_rules = {
    5: Rules(
        2,
        [
            Quest(2, 1),
            Quest(3, 1),
            Quest(2, 1),
            Quest(3, 1),
            Quest(3, 1),
        ],
    ),
    6: Rules(
        2,
        [
            Quest(2, 1),
            Quest(3, 1),
            Quest(4, 1),
            Quest(3, 1),
            Quest(4, 1),
        ],
    ),
    7: Rules(
        3,
        [
            Quest(2, 1),
            Quest(3, 1),
            Quest(3, 1),
            Quest(4, 2),
            Quest(4, 1),
        ],
    ),
    8: Rules(
        3,
        [
            Quest(3, 1),
            Quest(4, 1),
            Quest(4, 1),
            Quest(5, 2),
            Quest(5, 1),
        ],
    ),
    9: Rules(
        3,
        [
            Quest(3, 1),
            Quest(4, 1),
            Quest(4, 1),
            Quest(5, 2),
            Quest(5, 1),
        ],
    ),
    10: Rules(
        4,
        [
            Quest(3, 1),
            Quest(4, 1),
            Quest(4, 1),
            Quest(5, 2),
            Quest(5, 1),
        ],
    ),
}

MAX_QUEST_VOTES = 4


class Game:
    def __init__(
        self, players: List[Player], roles: List[Role], rules: Optional[Rules] = None
    ):
        self.players = players
        self.roles = roles
        self.active_rules = rules or _default_rules[len(players)]
        evils = self.active_rules.total_evil
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
        self.commander_order = itertools.cycle(self.players)

    async def broadcast(self, msg: str) -> None:
        await asyncio.gather(*[player.send(msg) for player in self.players])

    async def vote(self, onwhat: str, players: List[Player]) -> Dict[str, bool]:
        async def vote_one(player: Player) -> bool:
            return await player.input_vote(onwhat)

        results = await asyncio.gather(*[vote_one(player) for player in players])
        return {player.name: result for player, result in zip(self.players, results)}

    async def send_initial_info(self, idx: int) -> None:
        player, role = self.player_map[idx]
        await player.send(f"Welcome to Avalon, {player.name}!")
        await player.send(your_role(role))
        know = []
        for other_player, other_role in self.player_map:
            if other_player is player:
                continue
            if other_role.value.key in role.value.know:
                know.append(other_player.name)
        if know:
            await player.send("Here are the players you should know about:")
            await player.send(" ".join(know))

    async def nominate(self, quest: Quest) -> Tuple[List[Player], str]:
        commander = next(self.commander_order)
        await self.broadcast(f"The residing lord commander is {commander.name}")
        while True:
            nomination = await commander.input_players(
                f"Lord commander! Select {quest.num_players} knights to go on this quest!",
                quest.num_players,
            )
            knights = [player for player in self.players if player.name in nomination]
            if len(knights) == quest.num_players:
                knight_names = " ".join([k.name for k in knights])
                await self.broadcast(
                    f"The lord commander nominates {knight_names} for this quest!"
                )
                return knights, knight_names

    async def quest(self, quest: Quest) -> _Side:
        noun_s = "s" if quest.required_fails > 1 else ""
        verb_s = "" if quest.required_fails > 1 else "s"
        await self.broadcast(
            "\n".join(
                [
                    "=" * 40,
                    f"We are going on a quest!",
                    f"{quest.num_players} knights will go on this quest",
                    f"This quest will fail if {quest.required_fails} participant{noun_s} betray{verb_s} us",
                ]
            )
        )

        for itry in range(MAX_QUEST_VOTES):
            await self.broadcast(f"Vote #{itry+1} will begin shortly")
            knights, knight_names = await self.nominate(quest)
            go_vote = await self.vote(
                f"Should {knight_names} go on a quest?", self.players
            )
            ctr = collections.Counter(go_vote.values())
            go = ctr[True] > ctr[False]
            await self.broadcast(
                "\n".join(
                    [
                        f"The table voted thus:",
                        *[
                            k + ": " + ("aye" if v else "nay")
                            for k, v in go_vote.items()
                        ],
                        quest_goes(go),
                    ]
                )
            )
            if go:
                break
        else:
            await self.broadcast(
                "All votes have failed! The lord commander alone shall select the knights for the next quest!"
            )
            knights, knight_names = await self.nominate(quest)

        await self.broadcast(going_on_a_quest(knight_names))
        quest_vote = await self.vote("Betray the quest?", knights)
        ctr = collections.Counter(quest_vote.values())
        betrayals = ctr[True]
        if betrayals:
            await self.broadcast(f"We have been betrayed by {betrayals} knights")
        else:
            await self.broadcast("None of the knights betrayed us")
        if betrayals >= quest.required_fails:
            result = "failed"
            winner = _Side.EVIL
        else:
            result = "succeeded"
            winner = _Side.GOOD
        await self.broadcast(f"The quest {result}!")
        return winner

    async def play(self, quests: bool = True) -> None:
        await asyncio.gather(
            *[self.send_initial_info(idx) for idx in range(len(self.player_map))]
        )
        if not quests:
            return
        score: Dict[_Side, int] = {s: 0 for s in _Side}
        for quest_idx, quest in enumerate(self.active_rules.quests):
            winner = await self.quest(quest)
            score[winner] += 1
            await self.broadcast(
                "Current score:\n"
                + ("\n".join([(s.value + ": " + str(score[s])) for s in _Side]))
            )
            (leading_team, nr_wins) = max(score.items(), key=lambda item: item[1])
            if nr_wins > len(self.active_rules.quests) // 2:
                break
        else:
            raise ValueError("no victory")
        await self.broadcast(f"The {leading_team.value.lower()} team won!")
