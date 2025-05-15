import json
import asyncio
import traceback
import websockets

class CookedWS:
    connected: asyncio.Event

    wss: websockets.Server | None = None
    port: int | None = None

    listeners = []

    def __init__(self):
        self.connected = asyncio.Event()

    async def setup(self):
        self.wss = await websockets.serve(self._handle_connection, 'localhost', 0)
        self.port = list(self.wss.sockets)[0].getsockname()[1]

        asyncio.create_task(self.wss.serve_forever())


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
