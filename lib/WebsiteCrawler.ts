import { Page } from 'puppeteer';
import * as cheerio from 'cheerio';
import sample from 'lodash/sample.js';

export class WebsiteCrawler {
    private page: Page;
    private baseUrl: URL;

    private internalLinks: Set<string>;
    private visitedLinks: Set<string>;
    private candidateLinks: Set<string>;

    constructor(page: Page, url: string) {
        this.page = page;
        this.baseUrl = new URL(url);
    }

    async getInternalLinks(n: number): Promise<string[]> {
        this.internalLinks = new Set();
        this.visitedLinks = new Set();
        this.candidateLinks = new Set();

        // Add the base URL to the candidate links.
        this.candidateLinks.add(this._normalizeUrl(this.baseUrl));

        // Crawl the website until we have n internal links.
        while (this.internalLinks.size < n && this.candidateLinks.size > 0) {
            // Pick a random candidate link.
            const candidate = sample(Array.from(this.candidateLinks));
            if (!candidate) continue;

            // Remove the candidate link from the candidate links.
            this.candidateLinks.delete(candidate);

            // Avoid visiting the same link twice.
            if (this.visitedLinks.has(candidate)) continue;
            this.visitedLinks.add(candidate);

            // Visit the candidate link.
            const res = await this.page.goto(candidate);
            if (!res?.ok()) continue;

            // Ignore non-HTML links.
            if (!res.headers()['content-type']?.includes('text/html')) {
                continue;
            }

            // Add the candidate link to the internal links.
            this.internalLinks.add(candidate);

            // Find new candidate links.
            const content = await this.page.content();

            const links = this._getLinksFromContent(content);
            const internalLinks = links.filter(this._isInternalLink.bind(this));

            for (const link of internalLinks) {
                const normalizedLink = this._normalizeUrl(link);

                if (!this.visitedLinks.has(normalizedLink)) {
                    this.candidateLinks.add(normalizedLink);
                }
            }
        }

        return Array.from(this.internalLinks);
    }

    private _isInternalLink(url: URL) {
        return url.host === this.baseUrl.host;
    }

    private _getLinksFromContent(content: string): URL[] {
        const $ = cheerio.load(content);

        // Get all anchor tags and extract their href attributes.
        return $('a')
            .map((_, el) => $(el).attr('href'))
            .toArray()
            .filter(href => href)
            .map(href => this._getUrl(href));
    }

    private _normalizeUrl(url: URL): string {
        const normalized = new URL(url.href);

        // Remove query parameters (?query=value)
        normalized.search = '';

        // Remove fragments (#fragment)
        normalized.hash = '';

        return normalized.href;
    }

    private _getUrl(url: string) {
        return new URL(url, this.baseUrl);
    }
}