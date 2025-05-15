import asyncio
import os
import shutil
import json
import websockets
from typing import List, Optional, Dict, Any, Callable, Awaitable, Set

from playwright.async_api import async_playwright, BrowserContext, Page

from schema.cooked_consent_result import CookieConsentResult
from schema.consent_action import ConsentAction

class CookedCollector:
    def __init__(self, consent_action: ConsentAction = ConsentAction.OPT_OUT, websocket_port: int = 5630):
        self.consent_action = consent_action
        self.websocket_port = websocket_port
        self.websocket_server = None
        self.current_results = {
            "url": '',
            "popup_found": False,
            "action_taken": None,
            "success": None,
            "cmp_detected": None,
            "error": None,
            "cookies": set()
        }
        self.extension_path = os.path.abspath("extensions/autoconsent/dist/addon-mv3")
        self.on_result: Optional[Callable[[str, CookieConsentResult], Awaitable[None]]] = None
        
    async def start_websocket_server(self):
        self.websocket_server = await websockets.serve(self.handle_websocket_connection, 'localhost', self.websocket_port)
        print(f"WebSocket server started at ws://localhost:{self.websocket_port}")
    
    async def handle_websocket_connection(self, websocket, path=None):
        print(f"New WebSocket connection established from {websocket.remote_address}")
        try:
            # Send an initial message to set the consent action choice
            choice = self.consent_action.value if self.consent_action != ConsentAction.BASELINE else "none"
            await websocket.send(json.dumps({"type": "optChoice", "choice": choice}))
            print(f"Sent consent action choice: {choice}")
            
            # Listen for messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    # print(f"Received WebSocket message: {data}")
                    
                    # Handle different message types
                    if data.get('type') == 'popupFound':
                        url = data.get('message', {}).get('url')
                        cmp = data.get('message', {}).get('cmp')
                        self.current_results["popup_found"] = True
                        self.current_results["cmp_detected"] = cmp
                        print(f"Popup found on {url} with CMP: {cmp}")

                    elif data.get('type') == 'optResult':
                        url = data.get('message', {}).get('url')
                        result = data.get('message', {}).get('result')
                        self.current_results["action_taken"] = result
                        print(f"Consent action result for {url}: {result}")

                    elif data.get('type') == 'autoconsentDone':
                        url = data.get('message', {}).get('url')
                        self.current_results["success"] = True
                        print(f"Autoconsent done for {url}")
                    
                    elif data.get('type') == 'autoconsentError':
                        url = data.get('message', {}).get('url')
                        error = data.get('message', {}).get('error')
                        self.current_results.error = error
                        print(f"Error on {url}: {error}")
                    
                    # # Call the result handler if a result is updated and handler is set
                    # if data.get('type') in ['popupFound', 'optResult', 'autoconsentError']:
                    #     url = data.get('message', {}).get('url')
                    #     if url and url in self.current_results and self.on_result:
                    #         await self.on_result(url, self.current_results[url])
                except json.JSONDecodeError:
                    print(f"Received non-JSON message: {message}")
        
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"Error handling WebSocket connection: {e}")
    
    async def setup_browser(self):
        # Create a temporary user data directory
        user_data_dir = "/tmp/playwright-cooked-profile"
        # Remove the user data directory if it exists to start fresh
        if os.path.exists(user_data_dir):
            print(f"Removing existing user data directory: {user_data_dir}")
            shutil.rmtree(user_data_dir)
        print(f"Creating fresh user data directory: {user_data_dir}")
        os.makedirs(user_data_dir, exist_ok=True)
        
        # Launch the browser with the extension
        playwright = await async_playwright().start()
        browser_context = await playwright.chromium.launch_persistent_context(
            user_data_dir, 
            headless=False, 
            args=[f'--disable-extensions-except={self.extension_path}', f'--load-extension={self.extension_path}'],
            ignore_default_args=['--disable-extensions']
        )
        return playwright, browser_context
    
    async def get_cookies(self, page: Page):
        try:
            cookies = await page.context.cookies()
            return cookies
        except Exception as e:
            print(f"Error getting cookies: {e}")
            return ['error getting cookies']
    
    async def process_sites(self, browser_context: BrowserContext, sites: List[str], timeout: int = 30) -> Dict[str, Any]:
        # Create a new page
        page = await browser_context.new_page()

        self.current_results["url"] = sites[0]

        try:            
            # Navigate to the sites
            for site in sites:
                url = site
                print(f'Navigating to {url}')

                try:
                    await asyncio.wait_for(page.goto(url, wait_until='load'), timeout=timeout)
                    await asyncio.sleep(1)
                    # page.goto(url, wait_until='domcontentloaded')
                    # await page.waitForNavigation({waitUntil: 'networkidle0', });
                    cookies = await self.get_cookies(page)
                    for cookie in cookies:
                        self.current_results["cookies"].add(cookie['name'])
                    print(f"Collected {len(cookies)}")
                except Exception as e:
                    print(f"Error navigating to {url}: {e}")
                    self.current_results["error"] = f"Navigation error: {str(e)}"
            

            # Return the result for this URL
            
        finally:
            # Close the page

            await page.close()
            return self.current_results
