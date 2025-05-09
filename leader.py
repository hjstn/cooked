import os
import csv
import json
import time
import asyncio
import argparse

import pika
from pika.exceptions import UnroutableError

from lib.mq import CookedChannel, CookedMQ
from schema.cooked_result_internal_crawler import CookedResultInternalCrawler
from schema.cooked_task_internal_crawler import CookedTaskInternalCrawler

async def recv_crawler_results(mq: CookedMQ, results_filename: str, resume: bool = False):
    results_queue = CookedChannel[CookedResultInternalCrawler](mq, 'cooked_results_internal_crawler', fanout=True, purge=not resume)

    with open(results_filename, 'w', buffering=1) as results_file:
        for result, ack, nack in results_queue.consume():
            print(f"Writing result for {result.site} to file")

            results_file.write(f'{json.dumps(vars(result))}\n')

            ack()

async def send_crawler_tasks(mq: CookedMQ, resume: bool = False):
    with open(os.path.join('data', 'tranco_sample.csv'), 'r') as tranco_file:
        csv_reader = csv.DictReader(tranco_file)

        site_rows = [row for row in csv_reader]

    print(f'Loaded {len(site_rows)} sites from Tranco file')

    ic_queue = CookedChannel[CookedTaskInternalCrawler](mq, 'cooked_task_internal_crawler', purge=not resume)

    for site_row in site_rows:
        while True:
            try:
                ic_queue.send(CookedTaskInternalCrawler(**site_row))

                break
            except UnroutableError as e:
                print(f'Failed to send task: {e}')

                time.sleep(5)

    print('Sent all tasks to message queue')

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='localhost')
    parser.add_argument('--resume', action='store_true', default=False)
    parser.add_argument('--results', type=str, default='results/internal_links.jsonl')
    parser.add_argument('--username', type=str, default='ews')
    parser.add_argument('--password', type=str, default='')
    args = parser.parse_args()

    params = pika.ConnectionParameters(
        host=args.host,
        virtual_host='/',
        credentials=pika.credentials.PlainCredentials(args.username, args.password)
    )

    mq = CookedMQ(params, leader=True)

    print('Connected to message queue')

    await asyncio.gather(
        send_crawler_tasks(mq, resume=args.resume),
        recv_crawler_results(mq, resume=args.resume, results_filename=args.results)
    )

if __name__ == "__main__":
    asyncio.run(main())