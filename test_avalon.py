import asyncio
import collections
import contextlib
import enum
import functools
import itertools
import re
from typing import (
    AsyncIterator,
    Callable,
    Deque,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
)

import pytest

import avalon

T = TypeVar("T")


class InputChannel(Generic[T]):
    def __init__(self) -> None:
        self._prod: "asyncio.Future[None]" = asyncio.Future()
        self._cons: "asyncio.Future[T]" = asyncio.Future()

    async def produce(self, value: T) -> None:
        await self._prod
        self._cons.set_result(value)
        self._prod = asyncio.Future()

    async def consume(self) -> T:
        self._prod.set_result(None)
        value = await self._cons
        self._cons = asyncio.Future()
        return value


class Player(avalon.Player):
    def __init__(self, name: str):
        super().__init__(name)
        self.msgs: Deque[str] = collections.deque()
        self.wait_msgs: "asyncio.Future[None]" = asyncio.Future()
        self.role: Optional[avalon.Role] = None
        self.vote_channel: InputChannel[bool] = InputChannel()
        self.nominate_channel: InputChannel[List[str]] = InputChannel()

    async def send(self, msg: str) -> None:
        if not self.wait_msgs.done():
            self.wait_msgs.set_result(None)
        self.msgs.append(msg)

    async def input_players(self, msg: str, count: int) -> List[str]:
        await self.send(msg)
        return await self.nominate_channel.consume()

    async def input_vote(self, msg: str) -> bool:
        await self.send(msg)
        return await self.vote_channel.consume()

    async def consume_msgs(self) -> AsyncIterator[str]:
        while True:
            if not self.msgs:
                self.wait_msgs = asyncio.Future()
                await self.wait_msgs
            yield self.msgs.popleft()

    async def consume_msg_map(self, map: Dict[str, T]) -> T:
        async for s in self.consume_msgs():
            r = map.get(s.splitlines()[-1])
            if r is not None:
                return r
        assert False, "unreachable"

    _GET_ROLE = {avalon.your_role(role): role for role in avalon.Role}

    async def get_role(self) -> avalon.Role:
        if self.role is None:
            role = await self.consume_msg_map(self._GET_ROLE)
            self.role = role
        return self.role

    _QUEST_GOES = {avalon.quest_goes(b): b for b in [False, True]}

    async def quest_goes(self) -> bool:
        return await self.consume_msg_map(self._QUEST_GOES)

    _QUEST_RESULT = {avalon.quest_result(s): s for s in avalon.Side}

    async def quest_result(self) -> avalon.Side:
        return await self.consume_msg_map(self._QUEST_RESULT)

    _VICTORY = {avalon.victory(s): s for s in avalon.Side}

    async def victory(self) -> avalon.Side:
        return await self.consume_msg_map(self._VICTORY)

    async def expect_msg(self, msg: str) -> None:
        async for s in self.consume_msgs():
            if s == msg:
                return
        assert False, "unreachable"

    async def nominate(self, value: List[str]) -> None:
        await self.nominate_channel.produce(value)

    async def vote(self, value: bool) -> None:
        await self.vote_channel.produce(value)


RULES_1V1 = avalon.Rules(
    1,
    [
        avalon.Quest(1, 1),
        avalon.Quest(1, 1),
        avalon.Quest(1, 1),
    ],
)


class Vote(enum.Enum):
    TRUE = 0
    FALSE = 1
    TIE = 2


class Game(avalon.Game):

    def __init__(self, roles: List[avalon.Role]):
        self.tplayers = [Player(f"p{i}") for i in range(2)]
        self.tcommanders = itertools.cycle(self.tplayers)
        players: List[avalon.Player] = [p for p in self.tplayers]
        super().__init__(players, roles, RULES_1V1)

    async def role_ctr(self) -> "collections.Counter[avalon.Role]":
        roles = await asyncio.gather(*[p.get_role() for p in self.tplayers])
        return collections.Counter(roles)

    async def submit_votes(self, vote: Vote) -> None:
        def select_vote(i: int) -> bool:
            @functools.lru_cache()
            def map() -> Dict[Vote, Callable[[int], bool]]:
                return {
                    Vote.TRUE: (lambda i: True),
                    Vote.FALSE: (lambda i: False),
                    Vote.TIE: (lambda i: bool(i)),
                }

            return map()[vote](i)

        await asyncio.gather(
            *[p.vote(select_vote(i)) for i, p in enumerate(self.tplayers)]
        )

    async def prep_nomination(self) -> Player:
        commander = next(self.tcommanders)
        await commander.nominate([commander.name])
        return commander

    async def _prep_quest(self, vote: Vote) -> Tuple[bool, Player]:
        commander = await self.prep_nomination()
        await self.submit_votes(vote)
        goes = await self.tplayers[0].quest_goes()
        return goes, commander

    async def prep_quest(self, vote: Vote) -> bool:
        goes, _ = await self._prep_quest(vote)
        return goes

    async def run_quest(self, betray: bool) -> avalon.Side:
        _, commander = await self._prep_quest(Vote.TRUE)
        await commander.vote(betray)
        return await self.tplayers[0].quest_result()

    async def victory(self) -> avalon.Side:
        return await self.tplayers[0].victory()

    async def run_game(self, betray_per_mission: List[bool]) -> avalon.Side:
        for betray in betray_per_mission:
            await self.run_quest(betray)
        return await self.victory()


class TestAvalon:
    @pytest.mark.asyncio
    async def test_simple(self) -> None:
        game = Game([])
        await game.play(quests=False)
        ctr = await game.role_ctr()
        assert ctr[avalon.Role.Minion] == 1
        assert ctr[avalon.Role.Servant] == 1

    @pytest.mark.asyncio
    async def test_roles(self) -> None:
        roles = [
            avalon.Role.Merlin,
            avalon.Role.Assassin,
        ]
        game = Game(roles)
        await game.play(quests=False)
        ctr = await game.role_ctr()
        for role in roles:
            assert ctr[role] == 1

    @staticmethod
    @contextlib.contextmanager
    def game(roles: List[avalon.Role]) -> Iterator[Game]:
        game = Game(roles)
        task = asyncio.create_task(game.play())
        try:
            yield game
        finally:
            task.cancel()

    async def nomination_test(self, vote: Vote, expected: bool) -> None:
        with self.game([]) as game:
            goes = await game.prep_quest(vote)
            assert goes is expected

    @pytest.mark.asyncio
    async def test_nomination_pass(self) -> None:
        await self.nomination_test(Vote.TRUE, True)

    @pytest.mark.asyncio
    async def test_nomination_fail(self) -> None:
        await self.nomination_test(Vote.FALSE, False)

    @pytest.mark.asyncio
    async def test_nomination_tie(self) -> None:
        await self.nomination_test(Vote.TIE, False)

    @pytest.mark.asyncio
    async def test_nomination_retry(self) -> None:
        with self.game([]) as game:
            assert not await game.prep_quest(Vote.FALSE)
            assert await game.prep_quest(Vote.TRUE)

    @pytest.mark.asyncio
    async def test_nomination_force(self) -> None:
        with self.game([]) as game:
            for _ in range(avalon.MAX_QUEST_VOTES):
                assert not await game.prep_quest(Vote.FALSE)
            commander = await game.prep_nomination()
            await game.tplayers[0].expect_msg(avalon.going_on_a_quest(commander.name))

    async def quest_simple_test(self, betray: bool, expected: avalon.Side) -> None:
        with self.game([]) as game:
            result = await game.run_quest(betray)
            assert result is expected

    @pytest.mark.asyncio
    async def test_quest_success(self) -> None:
        await self.quest_simple_test(False, avalon.Side.GOOD)

    @pytest.mark.asyncio
    async def test_quest_failure(self) -> None:
        await self.quest_simple_test(True, avalon.Side.EVIL)

    async def full_game_test(
        self,
        roles: List[avalon.Role],
        betray_per_mission: List[bool],
        expected: avalon.Side,
    ) -> None:
        with self.game(roles) as game:
            result = await game.run_game(betray_per_mission)
            assert result is expected

    async def long_game_test(self, betray: bool, expected: avalon.Side) -> None:
        await self.full_game_test([], [True, False, betray], expected)

    @pytest.mark.asyncio
    async def test_long_game_good_victory(self) -> None:
        await self.long_game_test(False, avalon.Side.GOOD)

    @pytest.mark.asyncio
    async def test_long_game_evil_victory(self) -> None:
        await self.long_game_test(True, avalon.Side.EVIL)

    async def quick_game_test(self, betray: bool, expected: avalon.Side) -> None:
        await self.full_game_test([], [betray, betray], expected)

    @pytest.mark.asyncio
    async def test_quick_game_good_victory(self) -> None:
        await self.quick_game_test(False, avalon.Side.GOOD)

    @pytest.mark.asyncio
    async def test_quick_game_evil_victory(self) -> None:
        await self.quick_game_test(True, avalon.Side.EVIL)

    ASSASSIN_TEST_ROLES = [avalon.Role.Merlin, avalon.Role.Assassin]

    async def assassin_test(self, hit: bool, expected: avalon.Side) -> None:
        with self.game(self.ASSASSIN_TEST_ROLES) as game:
            map = {await player.get_role(): player for player in game.tplayers}
            await game.run_quest(False)
            await game.run_quest(False)
            assassin = map[avalon.Role.Assassin]
            merlin = map[avalon.Role.Merlin]
            await assassin.expect_msg(avalon.ASSASSINATE)
            murdered = merlin if hit else assassin
            await assassin.nominate([murdered.name])
            result = await game.victory()
            assert result is expected

    @pytest.mark.asyncio
    async def test_assassin_miss(self) -> None:
        await self.assassin_test(False, avalon.Side.GOOD)

    @pytest.mark.asyncio
    async def test_assassin_hit(self) -> None:
        await self.assassin_test(True, avalon.Side.EVIL)

    @pytest.mark.asyncio
    async def test_no_assassination_on_evil_win(self) -> None:
        await self.full_game_test(
            self.ASSASSIN_TEST_ROLES,
            [True, True],
            avalon.Side.EVIL,
        )

    async def too_many_roles_test(self, role: avalon.Role) -> None:
        with pytest.raises(ValueError):
            Game([role] * 2)

    @pytest.mark.asyncio
    async def test_too_many_good_roles(self) -> None:
        await self.too_many_roles_test(avalon.Role.Merlin)

    @pytest.mark.asyncio
    async def test_too_many_evil_roles(self) -> None:
        await self.too_many_roles_test(avalon.Role.Assassin)

    @pytest.mark.asyncio
    async def test_broken_rules(self) -> None:
        game = avalon.Game([], [], avalon.Rules(0, []))
        with pytest.raises(ValueError):
            await game.play()
