#! /usr/bin/python3

import asyncio
import socket
from typing import List, Set

import avalon


class CliPlayer(avalon.Player):
    def __init__(self, c: socket.socket):
        self.c = c
        name = asyncio.get_event_loop().run_until_complete(self.read())
        super().__init__(name)

    async def read(self) -> str:
        loop = asyncio.get_event_loop()
        data = b""
        while not data.endswith(b"\n"):
            data += await loop.sock_recv(self.c, 0x1000)
        return data.decode().strip()

    async def input(self) -> str:
        loop = asyncio.get_event_loop()
        await loop.sock_sendall(self.c, b"I\n")
        data = await self.read()
        return data

    async def input_players(
        self,
        msg: str,
        count: int,
        exclude: Set[str],
    ) -> List[str]:
        while True:
            await self.send(msg)
            reply = (await self.input()).split(" ")
            if len(reply) == count:
                return reply

    async def input_vote(self, msg: str) -> bool:
        await self.send(msg)
        return (await self.input()) == "+"

    async def send(self, msg: str) -> None:
        loop = asyncio.get_event_loop()
        print(self.name, msg)
        await loop.sock_sendall(self.c, b"P" + msg.encode() + b"\n")


ADDRESS = ("127.0.0.1", 7015)


def server() -> None:
    nplayers = 8
    roles = [
        avalon.Role.Merlin,
        avalon.Role.Mordred,
        avalon.Role.Morgana,
        avalon.Role.Percival,
        avalon.Role.Oberon,
    ]

    s = socket.socket()
    s.bind(ADDRESS)
    s.listen(nplayers)

    print(f"Waiting for {nplayers} players")
    players: List[avalon.Player] = []
    while len(players) < nplayers:
        c, _ = s.accept()
        c.setblocking(False)
        players.append(CliPlayer(c))
    players.sort(key=lambda player: player.name)
    asyncio.get_event_loop().run_until_complete(avalon.Game(players, roles).play())


def client(name: str) -> None:
    s = socket.socket()
    s.connect(ADDRESS)
    s.sendall(name.encode() + b"\n")
    data = b""
    while True:
        s.setblocking(not data)
        try:
            data += s.recv(0x100)
        except BlockingIOError:
            pass
        try:
            idx = data.index(b"\n")
        except ValueError:
            continue
        msg = data[:idx]
        op = msg[0:1]
        if op == b"P":
            print(msg[1:].decode())
        elif op == b"I":
            s.sendall(input("> ").encode() + b"\n")
        else:
            print(msg.decode())

        data = data[idx + 1 :]


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        server()
    else:
        client(*sys.argv[1:])
