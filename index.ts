import path from 'path';
import fs from 'fs/promises';
import { URL } from 'url';
import { parseTranco } from "./lib/tranco.ts";

import UserAgent from 'user-agents';
import puppeteer, { Browser, CDPSession, Page } from 'puppeteer';

import { CookedProtocolHost } from './lib/cooked_protocol.ts';

const optChoice = 'optOut';

// import { parseTranco } from "./lib/tranco.ts";
// import { WebsiteCrawler } from './lib/website_crawler.ts';

// const crawler = new WebsiteCrawler(page, 'https://adv-sec-sp25.nikita.phd/');

// const links = await crawler.getInternalLinks(20);
// console.log(links);

// await browser.close();

// (async () => {
//     const tranco_entries = await parseTranco('./tranco_sample.csv');

//     const test_entries = tranco_entries.slice(0, 2);

//     const browser = await puppeteer.launch({ headless: false });
//     const [page] = await browser.pages();

//     for (const { rank, site } of test_entries) {
//         console.log(site);

//         const crawler = new WebsiteCrawler(page, `https://${site}`);

//         const links = await crawler.getInternalLinks(20);

//         console.log(links);
//     }
// })();

class CookedBrowser {
    private extension: CookedProtocolHost;

    private browser: Browser;
    private page: Page;
    private cdp: CDPSession;

    static async create() {
        const cookedBrowser = new CookedBrowser();

        await cookedBrowser._launch();

        return cookedBrowser;
    }

    constructor() {
        this.extension = new CookedProtocolHost();

        this.extension.on('connection', () => {
            this.extension.send('optChoice', {
                choice: optChoice
            });
        });
    }

    private async _launch() {
        this.browser = await puppeteer.launch({
            headless: false,
            defaultViewport: null,
            args: [
                `--load-extension=${path.resolve('extensions/autoconsent/dist/addon-mv3')}`
            ],
            ignoreDefaultArgs: ['--disable-extensions']
        });

        [this.page] = await this.browser.pages();

        this.page.setUserAgent(new UserAgent().random().toString());
        this.cdp = await this.page.createCDPSession();
    }

    public async debug(url: string) {
        let reportListener: any;

        const reportResultPromise = new Promise<any>((resolve, reject) => {
            reportListener = (data: any) => {
                switch (data.state.lifecycle) {
                    case 'done':
                    case 'nothingDetected':
                        resolve({
                            cmps: data.state.detectedCmps,
                            popups: data.state.detectedPopups
                        });
                        break;
                    default:
                        return;
                }
            };
        });

        this.extension.on('report', reportListener);

        this.cdp.send('Network.clearBrowserCookies');

        const response = await this.page.goto(url);
        const report = await reportResultPromise;

        console.log(report);

        console.log(await this.browser.cookies());

        this.extension.removeListener('report', reportListener);
    }


    public async scanWebsites(urls: string[]): Promise<Map<string, string[]>> {
        const results = new Map<string, string[]>();
        let processed = 0;

        for (const url of urls) {
            try {
                processed++;
                console.log(`\nProcessing ${processed}/${urls.length}: ${url}`);

                let reportListener: any;
                const reportResultPromise = new Promise<any>((resolve, reject) => {
                    reportListener = (data: any) => {              
                        if (data.state.lifecycle === 'done' || data.state.lifecycle === 'nothingDetected') {
                            resolve({
                                cmps: data.state.detectedCmps,
                                popups: data.state.detectedPopups
                            });
                        }
                    };
                });

                this.extension.on('report', reportListener);
                await this.cdp.send('Network.clearBrowserCookies');
                await this.page.goto(url, { waitUntil: 'load', timeout: 30000 });
                
                const report = await reportResultPromise;
                const cookies = await this.browser.cookies();
                const cookieNames = cookies.map(cookie => cookie.name);
                
                results.set(url, cookieNames);
                
                this.extension.removeListener('report', reportListener);
                
                // Add a small delay between requests to avoid overwhelming the browser
                await new Promise(resolve => setTimeout(resolve, 1000));
                
            } catch (error) {
                console.error(`Error scanning ${url}:`, error);
                results.set(url, [`Error: ${error.message}`]);
            }
        }

        return results;
    }
}

const cookedBrowser = await CookedBrowser.create();

// Parse the Tranco list
const tranco_entries = await parseTranco('./tranco_sample.csv');

// Take first 10 websites from the list (adjust number as needed)
// const websites = tranco_entries
//     .slice(0, 10)
//     .map(entry => `https://${entry.site}`);
// Use all websites from the Tranco list
const websites = tranco_entries.map(entry => `https://${entry.site}`);

console.log(`Starting to scan ${websites.length} websites...`);

const results = await cookedBrowser.scanWebsites(websites);

const cookiesDir = 'results';
await fs.mkdir(cookiesDir, { recursive: true });

for (const [url, cookies] of results) {
    console.log(`\nWebsite: ${url}`);
    // console.log('Cookies found:', cookies.length);
    // console.log('Cookie names:', cookies);
    
    const websiteName = new URL(url).hostname.replace(/^www\./, '').replace(/\./g, '_');
    const fileName = path.join(cookiesDir, `${websiteName}_${optChoice}_cookies.txt`);
    
    try {
        await fs.writeFile(fileName, cookies.join('\n'), 'utf8');
        console.log(`Cookies written to ${fileName}`);
    } catch (error) {
        console.error(`Error writing to ${fileName}:`, error);
    }
}

console.log('\nScan completed!');
console.log(`Processed ${websites.length} websites`);
console.log(`Results saved in ${cookiesDir}/ directory`);
