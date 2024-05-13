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


class Side(enum.Enum):
    GOOD = "Good"
    EVIL = "Evil"


def quest_result(side: Side) -> str:
    if side is Side.GOOD:
        result = "succeeded"
    else:
        result = "failed"
    return f"The quest {result}!"


def victory(side: Side) -> str:
    return f"The {side.value.lower()} team won!"


_Role = collections.namedtuple("_Role", ["key", "name", "side", "know"])


class Role(enum.Enum):
    Minion = _Role(
        key="Minion",
        name="Minion of Mordred",
        side=Side.EVIL,
        know=("Minion", "Mordred", "Morgana", "Assassin"),
    )
    Servant = _Role(
        key="Servant",
        name="Servant of Arthur",
        side=Side.GOOD,
        know=(),
    )
    Merlin = _Role(
        key="Merlin",
        name="Merlin",
        side=Side.GOOD,
        know=("Minion", "Morgana", "Assassin", "Oberon"),
    )
    Mordred = _Role(
        key="Mordred",
        name="Mordred",
        side=Side.EVIL,
        know=("Minion", "Mordred", "Morgana", "Assassin"),
    )
    Morgana = _Role(
        key="Morgana",
        name="Morgana",
        side=Side.EVIL,
        know=("Minion", "Mordred", "Morgana", "Assassin"),
    )
    Percival = _Role(
        key="Percival",
        name="Percival",
        side=Side.GOOD,
        know=("Merlin", "Morgana"),
    )
    Assassin = _Role(
        key="Assassin",
        name="Assassin",
        side=Side.EVIL,
        know=("Minion", "Mordred", "Morgana", "Assassin"),
    )
    Oberon = _Role(
        key="Oberon",
        name="Oberon",
        side=Side.EVIL,
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
        evil_roles = [r for r in roles if r.value.side == Side.EVIL]
        good_roles = [r for r in roles if r.value.side == Side.GOOD]
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

    async def input_players(
        self,
        selector: Player,
        msg: str,
        count: int,
    ) -> List[Player]:
        group = await selector.input_players(msg, count)
        assert len(group) == count
        knights = [player for player in self.players if player.name in group]
        assert len(knights) == count
        return knights

    async def nominate(self, quest: Quest) -> Tuple[List[Player], str]:
        commander = next(self.commander_order)
        await self.broadcast(f"The residing lord commander is {commander.name}")
        knights = await self.input_players(
            commander,
            f"Lord commander! Select {quest.num_players} knights to go on this quest!",
            quest.num_players,
        )
        knight_names = " ".join([k.name for k in knights])
        await self.broadcast(
            f"The lord commander nominates {knight_names} for this quest!"
        )
        return knights, knight_names

    async def quest(self, quest: Quest) -> Side:
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
            winner = Side.EVIL
        else:
            winner = Side.GOOD
        await self.broadcast(quest_result(winner))
        return winner

    async def play(self, quests: bool = True) -> None:
        await asyncio.gather(
            *[self.send_initial_info(idx) for idx in range(len(self.player_map))]
        )
        if not quests:
            return
        score: Dict[Side, int] = {s: 0 for s in Side}
        for quest_idx, quest in enumerate(self.active_rules.quests):
            winner = await self.quest(quest)
            score[winner] += 1
            await self.broadcast(
                "Current score:\n"
                + ("\n".join([(s.value + ": " + str(score[s])) for s in Side]))
            )
            (leading_team, nr_wins) = max(score.items(), key=lambda item: item[1])
            if nr_wins > len(self.active_rules.quests) // 2:
                break
        else:
            raise ValueError("no victory")
        await self.broadcast(victory(leading_team))
