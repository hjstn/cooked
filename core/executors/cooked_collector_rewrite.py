import asyncio
import websockets

from playwright.async_api import BrowserContext, Page, Playwright, Worker

from core.ws.cooked_ws import CookedWS

class CookedCollectorRewrite:
    p: Playwright
    user_data_dir: str
    extension_path: str
    opt_choice: str | None

    context: BrowserContext

    extension_id: str
    extension_worker: Worker
    extension_background_page: Page

    ws: CookedWS

    def __init__(self, p: Playwright, user_data_dir: str, extension_path: str, opt_choice: str | None = None):
        self.p = p
        self.user_data_dir = user_data_dir
        self.extension_path = extension_path

        self.opt_choice = opt_choice

    async def setup(self):
        self.context = await self.p.chromium.launch_persistent_context(
            self.user_data_dir, 
            headless=False, 
            args=[f'--disable-extensions-except={self.extension_path}', f'--load-extension={self.extension_path}'],
            ignore_default_args=['--disable-extensions']
        )

        await self._setup_extension()
        await self._setup_websocket()
    
    async def visit(self, urls: list[str]):
        cookies = set()

        cmps = set()
        popups = set()

        pages_with_cmps = 0
        pages_with_popups = 0

        for url in urls:
            page_cookies, page_cmps, page_popups, _ = await self.visit_page(url)

            cookies.update(page_cookies)

            cmps.update(page_cmps)
            popups.update(page_popups)

            if len(page_cmps) > 0:
                pages_with_cmps += 1

            if len(page_popups) > 0:
                pages_with_popups += 1

        return cookies, cmps, popups, pages_with_cmps, pages_with_popups

    async def visit_page(self, url: str):
        autoconsent_finished = asyncio.Event()

        cmps = set()
        popups = set()
        result = False

        def handle_message(message: dict):
            match message['type']:
                case 'cmpDetected':
                    cmps.add(message['cmp'])
                case 'popupFound':
                    popups.add(message['cmp'])
                case 'optOutResult' | 'optInResult':
                    nonlocal result
                    result = result or message['result']
                case 'autoconsentDone' | 'autoconsentError':
                    autoconsent_finished.set()

        self.ws.listeners.append(handle_message)

        page = await self.context.new_page()
        await page.goto(url)

        _, pending = await asyncio.wait({ asyncio.create_task(autoconsent_finished.wait()), asyncio.create_task(asyncio.sleep(5)) }, return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

        self.ws.listeners.remove(handle_message)

        cookies = await page.context.cookies()
        cookie_names = [cookie['name'] for cookie in cookies if 'name' in cookie]

        return cookie_names, cmps, popups, result

    async def send_message(self, message: dict):
        return await self.extension_background_page.evaluate("""
            ([extensionId, message]) => {
                return new Promise((resolve) => chrome.runtime.sendMessage(extensionId, message, resolve));
            }
          """, [self.extension_id, message])
    
    async def _send_init(self, port: int):
        return await self.send_message({
            'type': 'cooked',
            'subtype': 'init',
            'port': port
        })
    
    async def _send_update_config(self, opt_choice: str | None):
        return await self.send_message({
            'type': 'cooked',
            'subtype': 'updateConfig',
            'configChange': {
                'autoAction': opt_choice
            }
        })

    async def _setup_websocket(self):
        self.ws = CookedWS()
        await self.ws.setup()

        if self.ws.port is not None:
            await self._send_init(self.ws.port)

        await self.ws.connected.wait()

    async def _setup_extension(self):
        self.extension_worker = self.context.service_workers[0]
        self.extension_id = self.extension_worker.url.split('/')[2]

        self.extension_background_page = await self.context.new_page()
        await self.extension_background_page.goto(f'chrome-extension://{self.extension_id}/_generated_background_page.html')

        await self._send_update_config(self.opt_choice)
