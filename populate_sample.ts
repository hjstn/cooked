import path from 'path';
import fs from 'node:fs';
import { fileURLToPath } from 'url';

import * as cheerio from 'cheerio';
import puppeteer, { Browser, BrowserContext, Page, HTTPResponse } from 'puppeteer';

import sample from 'lodash/sample.js';
import chunk from 'lodash/chunk.js';

import { parseTranco } from './lib/tranco.ts';

class Traverser {
    private static protocols = ['https', 'http'];

    private browser: Browser;

    constructor() {}

    async setup() {
        this.browser = await puppeteer.launch({
            protocolTimeout: 360_000,
            args: [
                '--disable-gpu'
            ]
        });
    }

    async close() {
        this.browser.close();
    }

    async traverseSite(site: string, n: number): Promise<string[] | undefined> {
        console.log(`Traverse: ${site}`);

        const context = await this.browser.createBrowserContext();

        const protocol = await this._scanProtocol(context, site);

        if (!protocol) {
            await context.close();
            return;
        }

        console.log(`Protocol (${site}): ${protocol}`);

        const url = this._constructUrl(protocol, site);

        const results = await this._scanSite(context, url, n);

        await context.close();

        return results;
    }

    async _scanSite(context: BrowserContext, initialUrl: string, n: number): Promise<string[]> {
        const page = await context.newPage();

        let results = new Set<string>();

        let frontier = new Set<string>();
        let visited = new Set<string>();

        frontier.add(initialUrl);

        while (frontier.size > 0 && results.size < n) {
            const candidate = sample(Array.from(frontier));
            if (!candidate) continue;

            frontier.delete(candidate);

            if (visited.has(candidate)) continue;
            visited.add(candidate);

            let { valid, neighbours } = await this._scanPage(page, candidate);

            if (valid) {
                results.add(candidate);
            }

            neighbours = neighbours
                .map(neighbour => this._normalizeUrl(neighbour, candidate))
                .filter(neighbour => neighbour !== undefined);

            for (const neighbour of neighbours) {
                frontier.add(neighbour);
            }
        }

        await page.close();

        return Array.from(results);
    }

    async _scanPage(page: Page, url: string): Promise<{ valid: boolean; neighbours: string[] }> {
        let res: HTTPResponse | null;
        let text: string | undefined;

        try {
            res = await page.goto(url, { waitUntil: 'load', timeout: 5000 });

            if (!res || !res.ok() || !res.headers()['content-type'].includes('text/html')) {
                return { valid: false, neighbours: [] };
            }

            text = await res.text();
        } catch (error) {
            console.error(`Scan, Error: ${url}`, error);

            return { valid: false, neighbours: [] };
        }

        return { valid: true, neighbours: this._getLinksFromContent(await text) };
    }

    _getLinksFromContent(content: string): string[] {
        const $ = cheerio.load(content);

        // Get all anchor tags and extract their href attributes.
        return $('a')
            .map((_, el) => $(el).attr('href'))
            .toArray()
            .filter(href => href);
    }

    _normalizeUrl(url: string, base: string): string | undefined {
        const normalized = new URL(url, base);

        // Remove query parameters (?query=value)
        normalized.search = '';

        // Remove fragments (#fragment)
        normalized.hash = '';

        if (normalized.host !== new URL(base).host) return undefined;

        return normalized.href;
    }

    async _scanProtocol(context: BrowserContext, site: string): Promise<string | undefined> {
        const page = await context.newPage();

        for (const protocol of Traverser.protocols) {
            const url = this._constructUrl(protocol, site);
            
            try {
                await page.goto(url, { waitUntil: 'load', timeout: 5000 });

                return protocol;
            } catch (error) {
                console.error(`Protocol, Error: ${url}`, error);
            }
        }

        await page.close();

        return undefined;
    }

    _constructUrl(protocol: string, site: string) {
        return `${protocol}://${site}`;
    }
}

const tranco_sample = await parseTranco('./tranco_sample.csv');

const traverser = new Traverser();
await traverser.setup();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const populated_file = fs.createWriteStream(path.join(__dirname, 'populated.txt'), { flags: 'a' });
const checkpoint_file = fs.createWriteStream(path.join(__dirname, 'checkpoint.txt'), { flags: 'w' });

const last_index = -1;

const tranco_chunked = chunk(tranco_sample, 10);

for (const [index, chunk] of tranco_chunked.entries()) {
    if (index <= last_index) continue;

    console.log(`Started processing chunk ${index}`);

    const chunk_result = await Promise.allSettled(
        chunk.map(async ({ rank, site }) => ({
            rank,
            site,
            urls: await traverser.traverseSite(site, 15)
        })
    ));

    for (const result of chunk_result) {
        if (result.status === 'rejected') {
            console.log('Rejected', result.reason);
            continue;
        }

        populated_file.write(`${JSON.stringify(result.value)}\n`);
    }
    
    checkpoint_file.write(`${index}\n`);
}

await traverser.close();