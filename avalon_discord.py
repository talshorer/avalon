#! /usr/bin/python3

import dataclasses
import os
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from typing_extensions import ParamSpec
import dotenv
import discord
import asyncio

import avalon

client = discord.Client(
    intents=discord.Intents(
        messages=True,
        message_content=True,
        guilds=True,
    ),
)


Member = Union[discord.User, discord.Member]


@dataclasses.dataclass
class NominationOption:
    nick: str
    name: str
    mention: str


EMPTY_NOMINATION = NominationOption("", "", "")

waiters: Dict[str, "asyncio.Future[discord.Message]"] = {}


def to_mention(member: Member) -> str:
    return f"<@{member.id}>"


class DiscordPlayer(avalon.Player):
    def __init__(self, member: Member):
        self.member = member
        self.map: Dict[int, NominationOption] = {}
        super().__init__(to_mention(member))

    def set_map(self, map: Dict[int, NominationOption]) -> None:
        self.map = map

    async def io(self, msg: str) -> discord.Message:
        waiters[self.name] = asyncio.Future()
        await self.send(msg)
        await waiters[self.name]
        return waiters.pop(self.name).result()

    async def input_players(self, msg: str) -> List[str]:
        msg += "\n" + "\n".join(
            [f"{i}: {option.nick} / {option.name}" for i, option in self.map.items()]
        )
        reply = await self.io(msg)
        ids = reply.content.split(" ")
        return [self.map.get(int(i), EMPTY_NOMINATION).mention for i in ids]

    async def input_vote(self, msg: str) -> bool:
        reply = await self.io(msg)
        return reply.content == "+"

    async def send(self, msg: str) -> None:
        await self.member.send(msg)


def get_member(part: str, mentions: List[Member]) -> Optional[Member]:
    for member in mentions:
        if part == to_mention(member):
            return member
    return None


def get_role(part: str) -> Optional[avalon.Role]:
    for role in avalon.Role:
        if part == role.value.key:
            return role
    return None


@client.event
async def on_message(message: discord.Message) -> None:
    if message.author == client.user:
        return
    if isinstance(message.channel, discord.DMChannel):
        await collect_input(message)
    elif isinstance(message.channel, discord.TextChannel):
        await summon(message)


async def summon(message: discord.Message) -> None:
    assert isinstance(message.channel, discord.TextChannel)
    trigger = "!avalon "
    content = message.content
    if content.startswith(trigger):
        print(f"Summon message on channel {message.channel.name}")
        print(f"Content: {content}")
        players: List[avalon.Player] = []
        roles = []
        for part in content.split()[1:]:
            member = get_member(part, message.mentions)
            if member is not None:
                players.append(DiscordPlayer(member))
                continue
            role = get_role(part)
            if role is not None:
                roles.append(role)
                continue
            await message.channel.send(f"Sorry, don't know what to do with {part}")
            return
        map = {}
        for i, player in enumerate(players):
            assert isinstance(player, DiscordPlayer)
            map[i] = NominationOption(
                nick=getattr(player.member, "nick", ""),
                name=player.member.name,
                mention=to_mention(player.member),
            )
        for player in players:
            assert isinstance(player, DiscordPlayer)
            player.set_map(map)
        await avalon.Game(players, roles).play()


async def collect_input(message: discord.Message) -> None:
    waiter = waiters.get(to_mention(message.author))
    if waiter:
        waiter.set_result(message)


@client.event
async def on_ready() -> None:
    assert client.user is not None
    print(f"{client.user.name} has connected to Discord!")


async def main() -> None:
    dotenv.load_dotenv()
    token = os.getenv("DISCORD_TOKEN_AVALON")
    assert token is not None
    await client.start(token)


if __name__ == "__main__":
    all_tasks = [
        main(),
    ]
    asyncio.get_event_loop().run_until_complete(asyncio.gather(*all_tasks))
