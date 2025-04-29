import path from 'path';

import UserAgent from 'user-agents';
import puppeteer, { Browser, CDPSession, Page } from 'puppeteer';

import { CookedProtocolHost } from './lib/cooked_protocol.ts';

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
                choice: 'optOut'
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

        for (const url of urls) {
            try {
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
                await this.page.goto(url);
                
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

const websites = [
    'https://illinois.edu',
    'https://www.economist.com/'
];

const results = await cookedBrowser.scanWebsites(websites);

for (const [url, cookies] of results) {
    console.log(`\nWebsite: ${url}`);
    console.log('Cookies found:', cookies.length);
    console.log('Cookie names:', cookies);
}
