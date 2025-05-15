import os
import asyncio
import tempfile

from playwright.async_api import async_playwright

from core.executors.cooked_collector_rewrite import CookedCollectorRewrite

async def handle_connection(websocket):
    async for message in websocket:
        print(f"Received message: {message}")

async def main():
    user_data_root = os.path.abspath('user_data_dirs')
    extension_path = os.path.abspath('extensions/autoconsent/dist/addon-mv3')

    os.makedirs(user_data_root, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=user_data_root) as user_data_dir:
        async with async_playwright() as p:
            collector = CookedCollectorRewrite(p, user_data_dir, extension_path, None)
            await collector.setup()

            r = await collector.visit(['https://amtrak.com/', 'https://db.de'])
            print(r)

if __name__ == '__main__':
  asyncio.run(main())