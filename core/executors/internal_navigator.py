from typing import List, Union

import random
from urllib.parse import urlparse, ParseResult

from playwright.async_api import BrowserContext

class CookedInternalNavigator():
    SCHEMES = ['https', 'http']
    SUBDOMAINS = [None, 'www']

    context: BrowserContext

    def __init__(self, context: BrowserContext):
        self.context = context
    
    async def visit(self, domain: str, n: int = 1) -> Union[List[str], None]:
        url_parsed = await self._url_detect(domain)

        if url_parsed is None:
            print(f'{domain}: Failed to detect connect')
            return None
        
        print(f'{domain}: Using protocol {url_parsed.scheme}')
        
        internal_links = []

        visited = set()
        candidates = [url_parsed]

        while len(candidates) and len(internal_links) < n:
            candidate_parsed = self._random_pop(candidates)
            candidate = candidate_parsed.geturl()

            if candidate in visited:
                continue

            visited.add(candidate)

            links = await self._links_search(candidate)

            # Ignore failed pages or non-HTML pages
            if links is None:
                continue

            internal_links.append(candidate_parsed)

            candidates.extend(await self._links_filter(candidate_parsed, links))

        return [link.geturl() for link in internal_links]

    async def _links_filter(self, url: ParseResult, links: List[str]):
        # Filter out external links
        links_parsed = [
            urlparse(link, scheme=url.scheme)
            for link in links
            if link is not None and isinstance(link, str)]

        normalized_links = set(
            link._replace(params='', query='', fragment='')
            for link in links_parsed if link.netloc == url.netloc
        )

        return list(normalized_links)

    async def _links_search(self, url: str) -> Union[List[str], None]:
        print(f'Visiting {url}')

        async with await self.context.new_page() as page:
            try:
                response = await page.goto(url, wait_until='load')

                await page.wait_for_timeout(1000)
            except Exception as e:
                print(f'Failed to visit: {url}, {e}')
                return None

            if 'text/html' not in response.headers.get('content-type', ''):
                print(f'Not a HTML page: {url}')
                return None

            try:
                a_tags = await page.query_selector_all('a')
            except Exception as e:
                print(f'Failed to get query selectors: {url}, {e}')
                return None

            hrefs = [await link.get_attribute('href') for link in a_tags]

            return hrefs
    
    async def _url_detect(self, domain: str):
        for scheme in self.SCHEMES:
            for subdomain in self.SUBDOMAINS:
                if subdomain is not None:
                    url = f'{subdomain}.{domain}'
                else:
                    url = domain

                # Parse domain as netloc rather than path
                url_parsed = urlparse(f'//{url}', scheme=self.SCHEMES[0])

                scheme_url = url_parsed._replace(scheme=scheme)

                landing_url = await self._connect_try(scheme_url.geturl())

                if landing_url is not None:
                    return landing_url
        
        return None

    async def _connect_try(self, url: str) -> Union[str, None]:
        async with await self.context.new_page() as page:
            try:
                await page.goto(url, wait_until='commit')

                return urlparse(page.url)
            except Exception as e:
                print(e)
                return None
    
    def _random_pop(self, lst: List[any]):
        i = random.randint(0, len(lst) - 1)

        elem = lst[i]

        lst[i] = lst[-1]
        lst.pop()

        return elem