#! /usr/bin/python3

import os
import dotenv
import discord
import asyncio

from . import avalon

client = discord.Client()


def to_mention(member):
    return f"<@{member.id}>"


class DiscordPlayer(avalon.Player):
    def __init__(self, member):
        self.member = member
        self.name = to_mention(member)

    async def input(self, kind=""):
        raise NotImplementedError

    async def send(self, msg):
        await self.member.send(msg)


def get_member(part, mentions):
    for member in mentions:
        if part == to_mention(member):
            return member


def get_role(part):
    for role in avalon.Role:
        if part == role.value.key:
            return role


@client.event
async def on_message(message):
    trigger = "!avalon "
    content = message.content
    if content.startswith(trigger):
        print(f"Summon message on channel {message.channel.name}")
        print(f"Content: {content}")
        players = []
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
            await message.channel.send(
                f"Sorry, don't know what to do with {part}")
            return
        await avalon.play(players, roles)


@client.event
async def on_ready():
    print(f'{client.user.name} has connected to Discord!')


async def main():
    dotenv.load_dotenv()
    token = os.getenv("DISCORD_TOKEN_AVALON")
    await client.start(token)


if __name__ == "__main__":
    all_tasks = [
        main(),
    ]
    asyncio.get_event_loop().run_until_complete(asyncio.gather(*all_tasks))
