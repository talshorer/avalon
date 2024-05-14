#! /usr/bin/python3

import asyncio
import enum
import os
import traceback
from typing import Any, Awaitable, Dict, List, Optional, Set, Union

import discord
import dotenv

import avalon

Member = Union[discord.User, discord.Member]


class NominationOption:
    def __init__(self, player: avalon.Player):
        assert isinstance(player, DiscordPlayer)
        self.nick = getattr(player.member, "nick", "")
        self.name = player.member.name
        self.mention = player.client.to_mention(player.member)


class DiscordPlayer(avalon.Player):
    def __init__(self, member: Member, client: "Client"):
        self.member = member
        self.options: List[NominationOption] = []
        self.client = client
        super().__init__(self.client.to_mention(member))

    def set_options(self, options: List[NominationOption]) -> None:
        self.options = options

    async def interact(self, aw: Awaitable[Any]) -> discord.Interaction:
        fut: asyncio.Future[discord.Interaction] = asyncio.Future()
        self.client.waiters[self.name] = fut
        await asyncio.gather(aw, fut)
        return fut.result()

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

        chosen: List[str] = []
        aw: Awaitable[Any] = self.member.send(content=content, view=view(chosen))
        for _ in range(count):
            interaction = await self.interact(aw)
            chosen.append(self.button_data(interaction))
            aw = interaction.response.edit_message(content=content, view=view(chosen))
        await aw
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

        interaction = await self.interact(
            self.member.send(content=content, view=view(False, None))
        )
        reply = Vote(self.button_data(interaction))
        await interaction.response.edit_message(content=content, view=view(True, reply))
        return Vote(reply) is Vote.YES

    async def send(self, msg: str) -> None:
        await self.member.send(msg)


class Client(discord.Client):
    def __init__(self) -> None:
        super().__init__(
            intents=discord.Intents(
                messages=True,
                message_content=True,
                guilds=True,
            ),
        )
        self.waiters: Dict[str, "asyncio.Future[discord.Interaction]"] = {}

    @staticmethod
    def to_mention(member: Member) -> str:
        return f"<@{member.id}>"

    def get_member(self, part: str, mentions: List[Member]) -> Optional[Member]:
        for member in mentions:
            if part == self.to_mention(member):
                return member
        return None

    @staticmethod
    def get_role(part: str) -> Optional[avalon.Role]:
        for role in avalon.Role:
            if part == role.value.key:
                return role
        return None

    @staticmethod
    def get_flag(part: str) -> Optional[avalon.Flag]:
        for flag in avalon.Flag:
            if part == flag.name:
                return flag
        return None

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return
        assert isinstance(message.channel, discord.TextChannel)
        trigger = "!avalon "
        content = message.content
        if content.startswith(trigger):
            print(f"Summon message on channel {message.channel.name}")
            print(f"Content: {content}")
            players: List[avalon.Player] = []
            roles = []
            flags: Set[avalon.Flag] = set()
            for part in content.split()[1:]:
                if (member := self.get_member(part, message.mentions)) is not None:
                    players.append(DiscordPlayer(member, self))
                    continue
                if (role := self.get_role(part)) is not None:
                    roles.append(role)
                    continue
                if (flag := self.get_flag(part)) is not None:
                    flags.add(flag)
                    continue
                await message.channel.send(
                    f"Sorry, don't know what to do with `{part}`"
                )
                return
            options = [NominationOption(player) for player in players]
            for player in players:
                assert isinstance(player, DiscordPlayer)
                player.set_options(options)
            try:
                await avalon.Game(players, roles, flags).play()
            except Exception:
                tb = traceback.format_exc()
                await message.channel.send(f"The kingdom has fallen!\n```{tb}```")

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        waiter = self.waiters.pop(self.to_mention(interaction.user), None)
        if waiter is not None:
            waiter.set_result(interaction)

    async def on_ready(
        self,
    ) -> None:
        assert self.user is not None
        print(f"{self.user.name} has connected to Discord!")


async def main() -> None:
    dotenv.load_dotenv()
    token = os.getenv("DISCORD_TOKEN_AVALON")
    assert token is not None
    await Client().start(token)


if __name__ == "__main__":
    all_tasks = [
        main(),
    ]
    asyncio.get_event_loop().run_until_complete(asyncio.gather(*all_tasks))
