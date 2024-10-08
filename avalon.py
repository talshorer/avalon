#! /usr/bin/python3

from __future__ import annotations

import abc
import asyncio
import collections
import dataclasses
import enum
import itertools
import random
from typing import Dict, Iterable, List, Optional, Set, Tuple

ASSASSINATE = "Select a member of the table to assasinate"


def quest_goes(go: bool) -> str:
    return "This quest will {}go forward".format("" if go else "not ")


def going_on_a_quest(knight_names: str) -> str:
    return f"{knight_names} are going on a quest!"


class Side(enum.Enum):
    GOOD = "Good"
    EVIL = "Evil"


@dataclasses.dataclass
class _Role:
    key: str
    name: str
    side: Side
    know: Iterable[str]


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


class Flag(enum.Enum):
    NoQuests = 1
    Lady = 2


class Player(abc.ABC):
    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    async def send(self, msg: str) -> None: ...

    @abc.abstractmethod
    async def input_players(
        self,
        msg: str,
        count: int,
        exclude: Set[str],
    ) -> List[str]: ...

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
LADY_BEGINS_AFTER = 1


class Game:
    def __init__(
        self,
        players: List[Player],
        roles: List[Role],
        flags: Optional[Set[Flag]] = None,
        rules: Optional[Rules] = None,
    ):
        self.players = players
        self.roles = roles
        self.active_rules = rules or _default_rules[len(players)]
        if flags is None:
            flags = set()
        self.flags = flags
        self.lady_excludes: Set[str] = set()
        self.set_next_lady_target(players[-1])
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

    def set_next_lady_target(self, player: Player) -> None:
        self.next_lady_target = player
        self.lady_excludes.add(player.name)

    @staticmethod
    def bold(s: str) -> str:
        return s

    @classmethod
    def quest_result(cls, side: Side) -> str:
        if side is Side.GOOD:
            result = "succeeded"
        else:
            result = "failed"
        return f"The quest {cls.bold(result)}!"

    @classmethod
    def victory(cls, side: Side) -> str:
        return f"The {cls.bold(side.value.lower())} team wins!"

    @classmethod
    def lady_reveal(cls, name: str, side: Side) -> str:
        return (
            f"The Lady of the Lake reveals that {name} is {cls.bold(side.name.lower())}"
        )

    @classmethod
    def your_role(cls, role: Role) -> str:
        return f"Your role is {cls.bold(role.value.name)}"

    async def broadcast(self, msg: str) -> None:
        await asyncio.gather(*[player.send(msg) for player in self.players])

    async def vote(self, onwhat: str, players: List[Player]) -> Dict[str, bool]:
        async def vote_one(player: Player) -> bool:
            return await player.input_vote(onwhat)

        results = await asyncio.gather(*[vote_one(player) for player in players])
        return {player.name: result for player, result in zip(players, results)}

    async def send_initial_info(self, idx: int) -> None:
        player, role = self.player_map[idx]
        await player.send(f"Welcome to Avalon, {player.name}!")
        await player.send(self.your_role(role))
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
        exclude: Optional[Set[str]],
    ) -> List[Player]:
        if exclude is None:
            exclude = set()
        group = await selector.input_players(msg, count, exclude)
        assert len(group) == count
        knights = [player for player in self.players if player.name in group]
        assert len(knights) == count
        return knights

    _num_to_word = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
    }

    async def nominate(self, quest: Quest) -> Tuple[List[Player], str]:
        commander = next(self.commander_order)
        await self.broadcast(f"The residing lord commander is {commander.name}")
        how_many = self.bold(f"{self._num_to_word[quest.num_players]} knights")
        knights = await self.input_players(
            commander,
            f"Lord commander! Select {how_many} to go on this quest!",
            quest.num_players,
            None,
        )
        knight_names = " ".join([k.name for k in knights])
        await self.broadcast(
            f"The lord commander nominates {knight_names} for this quest!"
        )
        return knights, knight_names

    @staticmethod
    def capitalize(s: str) -> str:
        return s[0].upper() + s[1:]

    _num_to_ordinal = {
        1: "first",
        2: "second",
        3: "third",
        4: "fourth",
    }

    @staticmethod
    def knight_s(n: int) -> str:
        return "knight" + ("s" if n > 1 else "")

    async def quest(self, quest: Quest) -> Side:
        verb_s = "" if quest.required_fails > 1 else "s"
        to_go = self.bold(
            f"{self.capitalize(self._num_to_word[quest.num_players])} knights"
        )
        to_betray = self.bold(
            f"{self._num_to_word[quest.required_fails]} {self.knight_s(quest.required_fails)} "
        )
        await self.broadcast(
            "\n".join(
                [
                    "=" * 40,
                    "We are going on a quest!",
                    f"{to_go} will go on this quest",
                    f"This quest will fail if {to_betray} betray{verb_s} us",
                ]
            )
        )

        for itry in range(MAX_QUEST_VOTES):
            await self.broadcast(
                f"The {self.bold(self._num_to_ordinal[itry+1])} vote for this quest will begin shortly"
            )
            knights, knight_names = await self.nominate(quest)
            go_vote = await self.vote(
                f"Should {knight_names} go on a quest?", self.players
            )
            ctr = collections.Counter(go_vote.values())
            go = ctr[True] > ctr[False]
            await self.broadcast(
                "\n".join(
                    [
                        "The table voted thus:",
                        *[
                            k + ": " + self.bold("aye" if v else "nay")
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
            how_many = self.bold(
                f"{self._num_to_word[betrayals]} {self.knight_s(betrayals)}"
            )
            await self.broadcast(f"We have been betrayed by {how_many}")
        else:
            none = self.bold("None")
            await self.broadcast(f"{none} of the knights betrayed us")
        if betrayals >= quest.required_fails:
            winner = Side.EVIL
        else:
            winner = Side.GOOD
        await self.broadcast(self.quest_result(winner))
        return winner

    async def lady_of_the_lake(self) -> None:
        target = self.next_lady_target
        await self.broadcast(f"The lady of the Lake visits {target.name}")
        (chosen,) = await self.input_players(
            target,
            "Whose allegiance would you like the Lady of the Lake to reveal?",
            1,
            self.lady_excludes,
        )
        (role,) = [role for player, role in self.player_map if player is chosen]
        await target.send(self.lady_reveal(chosen.name, role.value.side))
        await self.broadcast(
            f"The Lady of the Lake revealed the allegiance of {chosen.name} to {target.name}"
        )
        self.set_next_lady_target(chosen)

    async def last_ditch_assassination(self) -> bool:
        def find_player(role: Role) -> Optional[Player]:
            matches = [player for player, prole in self.player_map if prole is role]
            if len(matches) == 1:
                return matches[0]
            return None

        assassin = find_player(Role.Assassin)
        merlin = find_player(Role.Merlin)
        if not assassin or not merlin:
            return False
        await self.broadcast(
            "The forces of evil have one last chance to win by murdering Merlin"
        )
        (murdered,) = await self.input_players(assassin, ASSASSINATE, 1, None)
        merlin_dead = merlin is murdered
        yes_or_no = "not " if not merlin_dead else ""
        this_is_merlin = self.bold(f"This is {yes_or_no}Merlin!")
        await self.broadcast(
            f"The assassin has murdered {murdered.name}! {this_is_merlin}"
        )
        return merlin_dead

    async def play(self) -> None:
        await asyncio.gather(
            *[self.send_initial_info(idx) for idx in range(len(self.player_map))]
        )
        if Flag.NoQuests in self.flags:
            return
        score: Dict[Side, int] = {s: 0 for s in Side}
        for quest_idx, quest in enumerate(self.active_rules.quests):
            winner = await self.quest(quest)
            score[winner] += 1
            await self.broadcast(
                "Current score:\n"
                + ("\n".join([self.bold(s.value + ": " + str(score[s])) for s in Side]))
            )
            (leading_team, nr_wins) = max(score.items(), key=lambda item: item[1])
            if nr_wins > len(self.active_rules.quests) // 2:
                break
            if Flag.Lady in self.flags and quest_idx >= LADY_BEGINS_AFTER:
                await self.lady_of_the_lake()
        else:
            raise ValueError("no victory")
        if leading_team is Side.GOOD:
            if await self.last_ditch_assassination():
                leading_team = Side.EVIL
        await self.broadcast(self.victory(leading_team))
