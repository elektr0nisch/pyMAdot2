"""Asynchronous python library to control MA Lighting dot2 console."""

from __future__ import annotations

import aiohttp
import asyncio
import json
import hashlib


class Dot2:
    def __init__(self, session: aiohttp.ClientSession, address: str, password: str):
        self.session = session
        self.address = address
        self.password = hashlib.md5(password.encode("utf-8")).hexdigest()
        self._initializing = False
        self._readyEvent = asyncio.Event()
        self.initialized = False

    @classmethod
    async def create(
        cls, session: aiohttp.ClientSession, address: str, password: str
    ) -> Dot2:
        instance = cls(session, address, password)
        await instance.initialize()
        return instance

    async def initialize(self) -> None:
        """Initialize socket."""
        if self._initializing or self.initialized:
            raise RuntimeError("Currently initializing or already initialized")

        self._initializing = True
        self.initialized = False

        self.ws = await self.session.ws_connect(f"ws://{self.address}/?ma=1")
        self.listen_task = asyncio.create_task(self.listen())

        await self._readyEvent.wait()

        self.initialized = True
        self._initializing = False

    async def disconnect(self) -> None:
        await self.send({"requestType": "close", "session": self.session_id})
        self.listen_task.cancel()

    async def listen(self) -> None:
        while True:
            message = await self.ws.receive()

            if message.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(message.data)
                if "status" in data:
                    await self.send({"session": 0})

                if "session" in data:
                    self.session_id = data["session"]

                if "forceLogin" in data:
                    await self.send(
                        {
                            "requestType": "login",
                            "username": "remote",
                            "password": self.password,
                            "session": self.session_id,
                        }
                    )
                
                if "responseType" in data:
                    self._readyEvent.set()

    async def send(self, payload: dict) -> None:
        await self.ws.send_str(json.dumps(payload, separators=(',', ':')))

    async def command(self, command) -> None:
        await self.send(
            {"requestType": "command", "command": command, "session": self.session_id}
        )
