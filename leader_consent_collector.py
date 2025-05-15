import os
import json
import time
import asyncio
import argparse
from typing import List, Dict, Any, Set

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
        resume: Whether to resume from previous state
    """
    results_queue = CookedChannel[CookedResultConsentCollector](mq, 'cooked_consent_results', fanout=True, purge=not resume)

    with open(results_filename, 'a', buffering=1) as results_file:
        for result, ack, nack in results_queue.consume():
            site = result.url.replace('https://', '').replace('http://', '').split('/')[0]
            print(f"Writing consent result for {site} to file")

            # Convert result to JSON-serializable dict
            result_dict = {
                'url': result.url,
                'popup_found': result.popup_found,
                'action_taken': result.action_taken,
                'success': result.success,
                'error': result.error,
                'cmp_detected': result.cmp_detected,
                'cookies': list(result.cookies)
            }
            
            results_file.write(f'{json.dumps(result_dict)}\n')
            ack()

async def send_consent_tasks(mq: CookedMQ, internal_links_filename: str, previous_filename: str = None, 
                            action: CookedConsentAction = CookedConsentAction.OPT_OUT,
                            max_urls_per_site: int = 5, resume: bool = False):
    """
    Load website groups from internal_links.jsonl and send tasks to the message queue.
    
    Args:
        mq: The message queue connection
        internal_links_filename: File containing internal links data
        previous_filename: File containing previous results (for resuming)
        action: The consent action to take
        country: The country code for geolocation
        max_urls_per_site: Maximum number of URLs to process per site
        resume: Whether to resume from previous state
    """
    # Track sites that have already been processed
    processed_sites = set()
    
    # Load previously processed sites if resuming
    if resume and previous_filename and os.path.exists(previous_filename):
        try:
            with open(previous_filename, 'r') as f:
                for line in f:
                    if line.strip():
                        result = json.loads(line)
                        site = result.get('url', '').replace('https://', '').replace('http://', '').split('/')[0]
                        processed_sites.add(site)
            
            print(f'Loaded {len(processed_sites)} previously processed sites from {previous_filename}')
        except Exception as e:
            print(f'Error loading previous results: {e}')
    
    # Load internal links data
    if not os.path.exists(internal_links_filename):
        print(f'Error: Internal links file {internal_links_filename} not found')
        return
    
    # Read the internal links file
    sites_data = []
    with open(internal_links_filename, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    site_data = json.loads(line)
                    sites_data.append(site_data)
                except json.JSONDecodeError as e:
                    print(f'Error parsing JSON line: {e}')
    
    print(f'Loaded {len(sites_data)} sites from internal links file')
    
    # Set up the task queue
    task_queue = CookedChannel[CookedTaskConsentCollector](mq, 'cooked_consent_tasks', purge=not resume)
    
    # Process each site
    task_id = 1
    for site_data in sites_data:
        site = site_data.get('site', '')
        urls = site_data.get('urls', [])
        
        # Skip if already processed
        if site in processed_sites:
            print(f'Skipping {site} because it has already been processed')
            continue
        
        # Ensure URLs are properly formatted
        # print(site)

        formatted_urls = ['https://' + site]
        for url in urls:
            if url.startswith('http://') or url.startswith('https://'):
                formatted_urls.append(url)
            else:
                formatted_urls.append(f'https://{url}')
        
        # Limit the number of URLs per site
        if max_urls_per_site > 0 and len(formatted_urls) > max_urls_per_site:
            formatted_urls = formatted_urls[:max_urls_per_site]
        
        # Create the task
        task = CookedTaskConsentCollector(
            urls=formatted_urls,
            action=action
        )
        
        # Send the task to the queue with retry logic
        while True:
            try:
                task_queue.send(task)
                print(f'Sent task for {site} with {len(formatted_urls)} URLs')
                task_id += 1
                break
            except UnroutableError as e:
                print(f'Failed to send task: {e}')
                time.sleep(5)
    
    print(f'Sent {task_id-1} tasks to message queue')

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
    parser.add_argument('--username', type=str, default='guest', help='RabbitMQ username')
    parser.add_argument('--password', type=str, default='guest', help='RabbitMQ password')
    parser.add_argument('--action', type=str, choices=['optIn', 'optOut', 'none'], 
                        default='optOut', help='Consent action to take')
    parser.add_argument('--max-urls', type=int, default=5, 
                        help='Maximum number of URLs to process per site (0 for unlimited)')
    
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
            previous_filename=args.previous,
            action=consent_action,
            max_urls_per_site=args.max_urls,
            resume=args.resume
        ),
        recv_consent_results(
            mq, 
            results_filename=args.results,
            resume=args.resume
        )
    )

if __name__ == "__main__":
    asyncio.run(main())