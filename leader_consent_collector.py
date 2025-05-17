import os
import json
import time
import asyncio
import argparse

import pickle

import pika
from pika.exceptions import UnroutableError
import pandas as pd

from core.mq import CookedChannel, CookedMQ
from schema.cooked_task_consent_collector import CookedTaskConsentCollector
from schema.cooked_result_consent_collector import CookedResultConsentCollector
from schema.cooked_consent_action import CookedConsentAction

async def recv_consent_results(mq: CookedMQ, results_filename: str, resume: bool = False):
    """
    Receive cookie consent results from the message queue and write them to a file.
    
    Args:
        mq: The message queue connection
        results_filename: File to write results to
    """
    # results_queue = CookedChannel[CookedResultConsentCollector](mq, 'cooked_consent_results', fanout=True, purge=not resume)
    results_queue = CookedChannel[CookedResultConsentCollector](mq, 'cooked_results_consent_collector', purge=not resume)

    with open(results_filename, 'a', buffering=1) as results_file:
        for result, ack, nack in results_queue.consume():
            site = result.site
            print(f"Writing consent result for {site} to file")

            # Convert result to JSON-serializable dict
            result_dict = {
                "site": result.site,
                'action': result.action.value,
                'cookies': list(result.cookies),
                'cmps': list(result.cmps),
                'popups': list(result.popups),
                'pages_with_cmps': result.pages_with_cmps,
                'pages_with_popups': result.pages_with_popups,
                'success': result.success,
                'error': result.error
            }
            
            results_file.write(f'{json.dumps(result_dict)}\n')
            ack()

async def send_consent_tasks(mq: CookedMQ, internal_links_filename: str, action: CookedConsentAction, resume: bool = True, previous_filename: str = 'results/consent_results.jsonl'):
    crawled_sites = set()
    if os.path.exists(previous_filename):
        results = pd.read_json(os.path.abspath(previous_filename), lines=True)
        if not results.empty:
            crawled_sites = set(results['site'].tolist())

        print(f'Loaded {len(crawled_sites)} from previous results file: {previous_filename}')

    # Load internal links data
    if not os.path.exists(internal_links_filename):
        print(f'Error: Internal links file {internal_links_filename} not found')
        return
    
    sites_data = pd.read_json(internal_links_filename, lines=True).to_dict(orient='records')
    
    sites_data = sites_data.sample(frac=1).reset_index(drop=True)

    print(f'Loaded {len(sites_data)} sites from internal links file')

    # Set up the task queue
    task_queue = CookedChannel[CookedTaskConsentCollector](mq, 'cooked_task_consent_collector', purge=not resume)
    
    # Process each site
    for site_data in sites_data:
        site = site_data['site']
        urls = site_data.get('urls', [])

        if site in crawled_sites:
            continue

        # Create the task
        task = CookedTaskConsentCollector(
            site=site,
            urls=urls,
            action=action
        )

        print(f'Sending task for {site} ({action.value})')

        # Send the task to the queue with retry logic
        while True:
            try:
                task_queue.send(task)

                break
            except UnroutableError as e:
                print(f'Failed to send task: {e}')
                time.sleep(5)
    
    print(f'Sent all tasks to message queue')

async def main():
    """Main entry point for the consent leader."""
    parser = argparse.ArgumentParser(description='Cookie Consent Leader')
    parser.add_argument('--host', type=str, default='localhost', help='RabbitMQ host')
    parser.add_argument('--resume', action='store_true', default=False, help='Resume from previous state')
    parser.add_argument('--internal-links', type=str, default='results/internal_links.jsonl', 
                        help='File containing internal links data')
    parser.add_argument('--previous', type=str, default='results/consent_results.jsonl', 
                        help='File containing previous results (for resuming)')
    parser.add_argument('--results', type=str, default='results/consent_results.jsonl', 
                        help='File to write results to')
    parser.add_argument('--username', type=str, default='ews', help='RabbitMQ username')
    parser.add_argument('--password', type=str, default='', help='RabbitMQ password')
    parser.add_argument('--action', type=str, choices=['optIn', 'optOut', 'none'], 
                        default='optOut', help='Consent action to take')
    
    args = parser.parse_args()
    
    # Convert action string to enum
    try:
        consent_action = CookedConsentAction(args.action)
    except ValueError:
        print(f"Invalid action '{args.action}', defaulting to OPT_OUT")
        consent_action = CookedConsentAction.OPT_OUT

    # Set up RabbitMQ connection
    params = pika.ConnectionParameters(
        host=args.host,
        virtual_host='/',
        credentials=pika.credentials.PlainCredentials(args.username, args.password)
    )
    
    mq = CookedMQ(params, leader=True)
    print('Connected to message queue')
    
    # Create results directory if it doesn't exist
    os.makedirs(os.path.dirname(args.results), exist_ok=True)
    
    # Run the sender and receiver concurrently
    await asyncio.gather(
        send_consent_tasks(
            mq, 
            internal_links_filename=args.internal_links,
            action=consent_action,
            resume=args.resume,
            previous_filename=args.previous
        ),
        recv_consent_results(
            mq, 
            results_filename=args.results,
            resume=args.resume
        )
    )

if __name__ == "__main__":
    asyncio.run(main())