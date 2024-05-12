#! /usr/bin/python3

import asyncio
import dataclasses
import enum
import os
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

import discord
import dotenv
from typing_extensions import ParamSpec

import avalon

client = discord.Client(
    intents=discord.Intents(
        messages=True,
        message_content=True,
        guilds=True,
    ),
)


Member = Union[discord.User, discord.Member]


class NominationOption:
    def __init__(self, player: avalon.Player):
        assert isinstance(player, DiscordPlayer)
        self.nick = getattr(player.member, "nick", "")
        self.name = player.member.name
        self.mention = to_mention(player.member)


waiters: Dict[str, "asyncio.Future[discord.Interaction]"] = {}


def to_mention(member: Member) -> str:
    return f"<@{member.id}>"


class DiscordPlayer(avalon.Player):
    def __init__(self, member: Member):
        self.member = member
        self.options: List[NominationOption] = []
        super().__init__(to_mention(member))

    def set_options(self, options: List[NominationOption]) -> None:
        self.options = options

    def arm_waiter(self) -> None:
        waiters[self.name] = asyncio.Future()

    async def interact(self) -> discord.Interaction:
        await waiters[self.name]
        return waiters.pop(self.name).result()

    @staticmethod
    def button_data(interaction: discord.Interaction) -> str:
        assert interaction.data
        ret = interaction.data.get("custom_id")
        assert isinstance(ret, str)
        return ret

    async def input_players(self, content: str, count: int) -> List[str]:
        def view(chosen: List[str]) -> discord.ui.View:
            v = discord.ui.View()
            for opt in self.options:
                if opt.mention in chosen:
                    style = discord.ButtonStyle.success
                    disabled = True
                elif len(chosen) < count:
                    style = discord.ButtonStyle.primary
                    disabled = False
                else:
                    style = discord.ButtonStyle.secondary
                    disabled = True
                v.add_item(
                    discord.ui.Button(
                        label=f"{opt.nick} / {opt.name}",
                        custom_id=opt.mention,
                        disabled=disabled,
                        style=style,
                    )
                )
            return v

        self.arm_waiter()
        chosen: List[str] = []
        asyncio.create_task(self.member.send(content=content, view=view(chosen)))
        for _ in range(count):
            interaction = await self.interact()
            chosen.append(self.button_data(interaction))
            if len(chosen) < count:
                self.arm_waiter()
            asyncio.create_task(
                interaction.response.edit_message(content=content, view=view(chosen))
            )
        return chosen

    async def input_vote(self, content: str) -> bool:
        class Vote(enum.Enum):
            YES = "yes"
            NO = "no"

        def view(disabled: bool, success: Optional[Vote]) -> discord.ui.View:
            v = discord.ui.View()
            for item in Vote:
                if item is success:
                    style = discord.ButtonStyle.success
                elif disabled:
                    style = discord.ButtonStyle.secondary
                else:
                    style = discord.ButtonStyle.primary
                v.add_item(
                    discord.ui.Button(
                        label=item.value,
                        custom_id=item.value,
                        disabled=disabled,
                        style=style,
                    )
                )
            return v

        self.arm_waiter()
        asyncio.create_task(self.member.send(content=content, view=view(False, None)))
        interaction = await self.interact()
        reply = Vote(self.button_data(interaction))
        asyncio.create_task(
            interaction.response.edit_message(content=content, view=view(True, reply))
        )
        return Vote(reply) is Vote.YES

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
        options = [NominationOption(player) for player in players]
        for player in players:
            assert isinstance(player, DiscordPlayer)
            player.set_options(options)
        await avalon.Game(players, roles).play()


@client.event
async def on_interaction(interaction: discord.Interaction) -> None:
    waiter = waiters.get(to_mention(interaction.user))
    if waiter:
        waiter.set_result(interaction)


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
