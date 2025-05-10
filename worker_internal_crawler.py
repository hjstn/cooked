import asyncio
import argparse

import pika
from fake_useragent import UserAgent
from playwright.async_api import async_playwright

from core.mq import CookedChannel, CookedMQ
from core.executors import CookedInternalNavigator
from schema.cooked_result_internal_crawler import CookedResultInternalCrawler
from schema.cooked_task_internal_crawler import CookedTaskInternalCrawler


async def run_crawler_task(mq: CookedMQ, max_workers: int = 5):
    user_agent = UserAgent().chrome

    ic_queue = CookedChannel[CookedTaskInternalCrawler](mq, 'cooked_task_internal_crawler')
    results_queue = CookedChannel[CookedResultInternalCrawler](mq, 'cooked_results_internal_crawler')

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        semaphore = asyncio.Semaphore(max_workers)
        active_tasks = set()

        async def process_task(task, ack, nack):
            try:
                print(f'Starting work: {task.site}')
                
                context = await browser.new_context(user_agent=user_agent)
                
                try:
                    navigator = CookedInternalNavigator(context)
                    links = await navigator.visit(task.site, 15)
                    
                    if links is None:
                        print(f'Failed to crawl: {task.site}')
                        ack()
                        return
                        
                    results_queue.send(CookedResultInternalCrawler(**vars(task), urls=links))
                    ack()
                finally:
                    await context.close()
            finally:
                active_tasks.remove(current_task)

        while True:
            # Only consume new tasks if we have capacity
            if len(active_tasks) < max_workers:
                try:
                    task, ack, nack = next(ic_queue.consume())
                    current_task = asyncio.create_task(process_task(task, ack, nack))
                    active_tasks.add(current_task)
                except StopIteration:
                    # No more tasks in queue
                    if not active_tasks:
                        break
            
            # Wait for at least one task to complete if we're at capacity
            if len(active_tasks) >= 5 or active_tasks:
                done, pending = await asyncio.wait(
                    active_tasks, 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
            # If no tasks and no more in queue, we're done
            if not active_tasks:
                break

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

    await run_crawler_task(mq, max_workers=args.max_workers)

if __name__ == '__main__':
    asyncio.run(main())
