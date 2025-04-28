import path from 'path';

import UserAgent from 'user-agents';
import puppeteer, { Browser, Page } from 'puppeteer';

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
    }

    public async debug(url: string) {
        let reportListener;

        const reportResult = new Promise<void>((resolve, reject) => {
            reportListener = (data: any) => {
                switch (data.state.lifecycle) {
                    case 'done':
                    case 'nothingDetected':
                        resolve();
                        break;
                    default:
                        return;
                }
            };
        });

        this.extension.on('report', reportListener);

        this.page.goto(url);

        await reportResult;

        console.log('got some results');

        this.extension.removeListener('report', reportListener);
    }
}

const cookedBrowser = await CookedBrowser.create();

await cookedBrowser.debug("https://illinois.edu");

await cookedBrowser.debug("https://www.economist.com/");