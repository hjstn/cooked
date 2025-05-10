import asyncio
import argparse

import pika
from fake_useragent import UserAgent
from playwright.async_api import async_playwright

from core.mq import CookedChannel, CookedMQ
from core.executors import CookedInternalNavigator
from schema.cooked_result_internal_crawler import CookedResultInternalCrawler
from schema.cooked_task_internal_crawler import CookedTaskInternalCrawler


async def run_crawler_task(mq: CookedMQ):
    user_agent = UserAgent().chrome

    ic_queue = CookedChannel[CookedTaskInternalCrawler](mq, 'cooked_task_internal_crawler')
    results_queue = CookedChannel[CookedResultInternalCrawler](mq, 'cooked_results_internal_crawler')

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        for task, ack, nack in ic_queue.consume():
            print(f'Starting work: {task.site}')
            
            context = await browser.new_context(user_agent=user_agent)
            
            try:
                navigator = CookedInternalNavigator(context)
                links = await navigator.visit(task.site, 15)
                
                if links is None:
                    print(f'Failed to crawl: {task.site}')
                    ack()
                    continue
                    
                results_queue.send(CookedResultInternalCrawler(**vars(task), urls=links))
                ack()
            finally:
                await context.close()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='localhost')
    parser.add_argument('--username', type=str, default='ews')
    parser.add_argument('--password', type=str, default='')
    parser.add_argument('--max-workers', type=int, default=5)
    args = parser.parse_args()

    params = pika.ConnectionParameters(
        host=args.host,
        virtual_host='/',
        credentials=pika.credentials.PlainCredentials(args.username, args.password)
    )

    mq = CookedMQ(params)

    await asyncio.gather(*[
        run_crawler_task(mq)
        for _ in range(args.max_workers)
    ])

if __name__ == '__main__':
    asyncio.run(main())
