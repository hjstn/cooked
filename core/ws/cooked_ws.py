import json
import asyncio
import traceback
import websockets

class CookedWS:
    def __init__(self):
        self.connected: asyncio.Event = asyncio.Event()

        self.wss: websockets.Server | None = None
        self.port: int | None = None

        self.server_task: asyncio.Task | None = None

        self.listeners = []

    async def setup(self):
        self.wss = await websockets.serve(self._handle_connection, 'localhost', 0)
        self.port = list(self.wss.sockets)[0].getsockname()[1]

        self.server_task = asyncio.create_task(self.wss.serve_forever())
    
    async def close(self):
        if self.server_task is not None:
            self.server_task.cancel()

        if self.wss is not None:
            self.wss.close()
            await self.wss.wait_closed()

    async def _handle_connection(self, websocket: websockets.ServerConnection):
        self.connected.set()

        try:
            async for message in websocket:
                data = json.loads(message)

                for listener in self.listeners:
                    listener(data)
        except websockets.exceptions.ConnectionClosed:
            self.connected.clear()
        except Exception as e:
            print(traceback.format_exc())
