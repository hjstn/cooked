import os
import asyncio
import tempfile

from fake_useragent import UserAgent

from playwright.async_api import async_playwright

from core.executors.cooked_collector import CookedCollector
from schema.cooked_consent_action import CookedConsentAction
from schema.cooked_result_consent_collector import CookedResultConsentCollector
from schema.cooked_task_consent_collector import CookedTaskConsentCollector

async def main():
    user_data_root = os.path.abspath('user_data_dirs')
    os.makedirs(user_data_root, exist_ok=True)

    extension_path = os.path.abspath('extensions/autoconsent/dist/addon-mv3')

    user_agent = UserAgent().chrome

    tasks = [
        CookedTaskConsentCollector(
            site='amtrak.com',
            urls=['https://amtrak.com/', 'https://www.amtrak.com/regions/midwest.html'],
            action=CookedConsentAction.OPT_OUT
        ),
        CookedTaskConsentCollector(
            site='amtrak.com',
            urls=['https://amtrak.com/', 'https://www.amtrak.com/regions/midwest.html'],
            action=CookedConsentAction.OPT_IN
        )
    ]

    
    async with async_playwright() as p:
        for task in tasks:
            with tempfile.TemporaryDirectory(dir=user_data_root, ignore_cleanup_errors=True) as user_data_dir:
                print(f'Starting task for {task.urls[0]}')
                collector = CookedCollector(p, user_agent, user_data_dir, extension_path, task.action)
                await collector.setup()

                cookies, cmps, popups, pages_with_cmps, pages_with_popups = await collector.visit(task.urls)
                
                result = CookedResultConsentCollector(
                    site=task.site,
                    action=task.action,

                    cookies=cookies,
                    cmps=cmps,
                    popups=popups,

                    pages_with_cmps=pages_with_cmps,
                    pages_with_popups=pages_with_popups,

                    success=True,
                    error=None
                )

                await collector.close()

                print(len(result.cookies))

if __name__ == '__main__':
  asyncio.run(main())