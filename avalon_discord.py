#! /usr/bin/python3

import os
from typing import Any, Callable, List, Optional, TypeVar, Union
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


def to_mention(member: Member) -> str:
    return f"<@{member.id}>"


class DiscordPlayer(avalon.Player):
    def __init__(self, member: Member):
        self.member = member
        super().__init__(to_mention(member))

    async def input(self, kind: str) -> str:
        raise NotImplementedError

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
    trigger = "!avalon "
    content = message.content
    if not isinstance(message.channel, discord.TextChannel):
        return
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
        await avalon.Game(players, roles).play()


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
