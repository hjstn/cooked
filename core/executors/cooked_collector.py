from typing import Any, Tuple, TypeVar, Union

import asyncio

from playwright.async_api import BrowserContext, Page, Playwright, Worker

from core.ws.cooked_ws import CookedWS
from schema.cooked_consent_action import CookedConsentAction

T = TypeVar('T')

class CookedCollector:
    p: Playwright
    user_agent: str

    user_data_dir: str
    extension_path: str
    opt_choice: CookedConsentAction

    context: BrowserContext

    extension_id: str
    extension_worker: Worker
    extension_background_page: Page

    ws: CookedWS

    def __init__(self, p: Playwright, user_agent: str, user_data_dir: str, extension_path: str, opt_choice: CookedConsentAction = CookedConsentAction.BASELINE):
        self.p = p
        self.user_agent = user_agent

        self.user_data_dir = user_data_dir
        self.extension_path = extension_path

        self.opt_choice = opt_choice

    async def setup(self) -> None:
        self.context = await self.p.chromium.launch_persistent_context(
            self.user_data_dir,
            headless=False,
            user_agent=self.user_agent,
            args=[f'--disable-extensions-except={self.extension_path}', f'--load-extension={self.extension_path}'],
            ignore_default_args=['--disable-extensions']
        )

        await self._setup_extension()
        await self._setup_websocket()
    
    async def close(self) -> None:
        await self.context.close()
        await self.ws.close()
    
    async def visit(self, urls: list[str]) -> Tuple[set[str], set[str], set[str], int, int]:
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

    async def visit_page(self, url: str) -> Tuple[set[str], set[str], set[str], bool]:
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

        async with await self.context.new_page() as page:
            await page.goto(url)

            # wait until autoconsent is done, or 1 second has passed
            await self._await_timeout(asyncio.create_task(autoconsent_finished.wait()), timeout=1)

            # wait one more second to stabilize
            await asyncio.sleep(1)

            self.ws.listeners.remove(handle_message)

            cookies = await self._get_cookies(page)

            await page.close()

        return cookies, cmps, popups, result

    async def send_message(self, message: dict) -> Any:
        return await self.extension_background_page.evaluate("""
            ([extensionId, message]) => {
                return new Promise((resolve) => chrome.runtime.sendMessage(extensionId, message, resolve));
            }
          """, [self.extension_id, message])
    
    async def _send_init(self, port: int) -> bool:
        return await self.send_message({
            'type': 'cooked',
            'subtype': 'init',
            'port': port
        })
    
    async def _send_update_config(self, opt_choice: CookedConsentAction) -> bool:
        return await self.send_message({
            'type': 'cooked',
            'subtype': 'updateConfig',
            'configChange': {
                'autoAction': self._get_opt_value(opt_choice)
            }
        })

    async def _get_opt_value(self, opt_choice: CookedConsentAction) -> Union[str, None]:
        match opt_choice:
            case CookedConsentAction.BASELINE:
                return None
            case CookedConsentAction.OPT_IN:
                return 'optIn'
            case CookedConsentAction.OPT_OUT:
                return 'optOut'

    async def _setup_websocket(self) -> None:
        self.ws = CookedWS()
        await self.ws.setup()

        if self.ws.port is not None:
            await self._send_init(self.ws.port)

        await self.ws.connected.wait()

    async def _setup_extension(self) -> None:
        self.extension_worker = self.context.service_workers[0]
        self.extension_id = self.extension_worker.url.split('/')[2]

        self.extension_background_page = await self.context.new_page()
        await self.extension_background_page.goto(f'chrome-extension://{self.extension_id}/_generated_background_page.html')

        await self._send_update_config(self.opt_choice)

    async def _get_cookies(self, page: Page) -> set[str]:
        return set(cookie['name'] for cookie in await page.context.cookies() if 'name' in cookie)

    async def _await_timeout(self, task: asyncio.Task[T], timeout: int) -> T | None:
        done, pending = await asyncio.wait({ task, asyncio.create_task(asyncio.sleep(timeout)) }, return_when=asyncio.FIRST_COMPLETED)

        for pending_task in pending:
            pending_task.cancel()

        if task in done:
            return task.result()
        else:
            return None