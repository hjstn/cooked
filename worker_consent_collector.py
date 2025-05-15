import asyncio
import argparse
import logging
import os
import sys

import pika
from playwright.async_api import async_playwright, Browser, BrowserContext

from core.mq import CookedChannel, CookedMQ
from core.executors.cooked_collector import CookedCollector
from schema.cooked_consent_task import CookedConsentTask
from schema.cooked_consent_result import CookieConsentResult
from schema.consent_action import ConsentAction

async def run_consent_task(mq: CookedMQ):
    # Set up task and result queues
    task_queue = CookedChannel[CookedConsentTask](mq, 'cooked_consent_tasks')
    results_queue = CookedChannel[CookieConsentResult](mq, 'cooked_consent_results')
    

    for task, ack, nack in task_queue.consume():
        print(f'Starting work: {task.urls[0]}')

        # Create the collector with the specified consent action
        collector = CookedCollector(mq, task.action)
        
        # Start the WebSocket server
        await collector.start_websocket_server()    
        playwright, browser_context = await collector.setup_browser()
        
        try:
            # Process the sites
            result = await collector.process_sites(browser_context, task.urls)
            
            # Save the result to a file
            print(result)

            results_queue.send(CookieConsentResult(**result))
            ack()

        finally:
            # Clean up
            await browser_context.close()
            await playwright.stop()
            
            # Stop the WebSocket server
            collector.websocket_server.close()
            await collector.websocket_server.wait_closed()
            print("WebSocket server closed")

async def main():
    """Main entry point for the consent worker."""
    parser = argparse.ArgumentParser(description='Cookie Consent Worker')
    parser.add_argument('--host', type=str, default='localhost', help='RabbitMQ host')
    parser.add_argument('--username', type=str, default='guest', help='RabbitMQ username')
    parser.add_argument('--password', type=str, default='guest', help='RabbitMQ password')
    parser.add_argument('--max-workers', type=int, default=3, help='Maximum number of concurrent workers')
    parser.add_argument('--websocket-port', type=int, default=5630, help='WebSocket server port')
    
    args = parser.parse_args()
    
    # Set up RabbitMQ connection
    params = pika.ConnectionParameters(
        host=args.host,
        virtual_host='/',
        credentials=pika.credentials.PlainCredentials(args.username, args.password)
    )
    
    mq = CookedMQ(params)

    async with async_playwright() as p:
        await asyncio.gather(*[run_consent_task(mq) for _ in range(args.max_workers)])

if __name__ == '__main__':
    asyncio.run(main())
