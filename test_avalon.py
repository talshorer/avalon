import asyncio
import collections
import re
from typing import AsyncIterator, Deque, Dict, List, Optional, TypeVar

import pytest

import avalon

T = TypeVar("T")


class Player(avalon.Player):
    def __init__(self, name: str):
        super().__init__(name)
        self.msgs: Deque[str] = collections.deque()
        self.wait_msgs: "asyncio.Future[None]" = asyncio.Future()
        self.role: Optional[avalon.Role] = None

    async def send(self, msg: str) -> None:
        self.msgs.append(msg)

    async def input_players(self, msg: str, count: int) -> List[str]:
        raise NotImplementedError

    async def input_vote(self, msg: str) -> bool:
        raise NotImplementedError

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


RULES_1V1 = avalon.Rules(
    1,
    [
        avalon.Quest(1, 1),
        avalon.Quest(1, 1),
        avalon.Quest(1, 1),
    ],
)


class Game(avalon.Game):

    def __init__(self, roles: List[avalon.Role]):
        self.tplayers = [Player(f"p{i}") for i in range(2)]
        players: List[avalon.Player] = [p for p in self.tplayers]
        super().__init__(players, roles, RULES_1V1)

    async def role_ctr(self) -> "collections.Counter[avalon.Role]":
        roles = await asyncio.gather(*[p.get_role() for p in self.tplayers])
        return collections.Counter(roles)


class TestAvalon:
    @pytest.mark.asyncio
    async def test_simple(self) -> None:
        game = Game([])
        await game.play(quests=False)
        ctr = await game.role_ctr()
        assert ctr[avalon.Role.Minion] == 1
        assert ctr[avalon.Role.Servant] == 1
