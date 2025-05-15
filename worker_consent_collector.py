import asyncio
import argparse
import tempfile

import pika
from pika.credentials import PlainCredentials

from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Playwright

from core.executors.cooked_collector import CookedCollector
from core.mq import CookedChannel, CookedMQ

from schema.cooked_task_consent_collector import CookedTaskConsentCollector
from schema.cooked_result_consent_collector import CookedResultConsentCollector

async def run_consent_task(mq: CookedMQ, p: Playwright, user_data_root: str, extension_path: str):
    user_agent = UserAgent().chrome

    # Set up task and result queues
    task_queue = CookedChannel[CookedTaskConsentCollector](mq, 'cooked_task_consent_collector')
    results_queue = CookedChannel[CookedResultConsentCollector](mq, 'cooked_results_consent_collector')


    for task, ack, nack in task_queue.consume():

        print("consuming")
        with tempfile.TemporaryDirectory(dir=user_data_root) as user_data_dir:
            print(f'Starting work: {task.site}')
            
            collector = CookedCollector(p, user_agent, user_data_dir, extension_path, task.action)
            await collector.setup()

            try:
                cookies, cmps, popups, pages_with_cmps, pages_with_popups = await collector.visit(task.urls)

                results_queue.send(CookedResultConsentCollector(
                    site=task.site,
                    action=task.action,

                    cookies=cookies,
                    cmps=cmps,
                    popups=popups,

                    pages_with_cmps=pages_with_cmps,
                    pages_with_popups=pages_with_popups,

                    success=True,
                    error=None
                ))
                ack()
            finally:
                await collector.close()
            

async def main():
    """Main entry point for the consent worker."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='localhost', help='RabbitMQ host')
    parser.add_argument('--username', type=str, default='guest', help='RabbitMQ username')
    parser.add_argument('--password', type=str, default='guest', help='RabbitMQ password')
    parser.add_argument('--user-data-root', type=str, default='user_data_dirs', help='Root directory for user data')
    parser.add_argument('--extension-path', type=str, default='extensions/autoconsent/dist/addon-mv3', help='Path to the AutoConsent extension')
    parser.add_argument('--max-workers', type=int, default=1, help='Maximum number of concurrent workers')

    args = parser.parse_args()
    
    # Set up RabbitMQ connection
    params = pika.ConnectionParameters(
        host=args.host,
        virtual_host='/',
        credentials=PlainCredentials(args.username, args.password)
    )
    
    mq = CookedMQ(params)

    async with async_playwright() as p:
        await asyncio.gather(*[run_consent_task(mq, p, args.user_data_root, args.extension_path) for _ in range(args.max_workers)])

if __name__ == '__main__':
    asyncio.run(main())
