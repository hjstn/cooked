import path from 'path';
import fs from 'fs/promises';
import { URL } from 'url';
import { parseTranco } from "./lib/tranco.ts";

import * as zmq from 'zeromq';

import UserAgent from 'user-agents';
import puppeteer, { Browser, CDPSession, Page } from 'puppeteer';

import { CookedProtocolHost } from './lib/cooked_protocol.ts';

const optChoice = 'optIn';

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
            headless: true,
            protocolTimeout: 360_000,
            defaultViewport: null,
            args: [
                `--load-extension=${path.resolve('extensions/autoconsent/dist/addon-mv3')}`,
                '--disable-gpu'
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

        const response = await this.page.goto(url, { waitUntil: 'load', timeout: 30000 });
        const report = await reportResultPromise;

        console.log(report);

        console.log(await this.browser.cookies());

        this.extension.removeListener('report', reportListener);
    }

    public async scanRelatedWebsiteGroup(group: {rank: number, site: string, urls: string[]}): Promise<void | string[]> {
        if (!group.urls || group.urls.length === 0) {
            console.log(`No related URLs for ${group.site}, skipping`);
            return;
        }

        try {
            // Clear cookies before starting a new group
            await this.cdp.send('Network.clearBrowserCookies');
            
            // Process each related URL in the group
            for (const url of group.urls) {
                console.log(`  Visiting: ${url}`);
                
                let reportListener: any;
                const reportResultPromise = new Promise<any>((resolve, reject) => {
                    const timeoutId = setTimeout(() => {
                        resolve({
                            cmps: [],
                            popups: []
                        });
                    }, 30000);

                    reportListener = (data: any) => {              
                        if (data.state.lifecycle === 'done' || data.state.lifecycle === 'nothingDetected') {
                            clearTimeout(timeoutId);
                            resolve({
                                cmps: data.state.detectedCmps,
                                popups: data.state.detectedPopups
                            });
                        }
                    };
                });

                this.extension.on('report', reportListener);
                
                try {
                    await this.page.goto(url, { waitUntil: 'load', timeout: 30000 });
                    await reportResultPromise;
                } catch (error) {
                    console.error(`  Error visiting ${url}: ${error.message}`);
                } finally {
                    this.extension.removeListener('report', reportListener);
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
            
            // After visiting all related URLs, collect all cookies
            const cookies = await this.browser.cookies();
            const cookieNames = cookies.map(cookie => cookie.name);

            return cookieNames;
        } catch (error) {
            console.error(`Error processing group ${group.site}:`, error);

            return;
        }
    }

    public async scanRelatedWebsiteGroups(websiteGroups: Array<{rank: number, site: string, urls: string[]}>): Promise<Map<string, string[]>> {
        const results = new Map<string, string[]>();
        let processedGroups = 0;

        // Create results directory
        const cookiesDir = 'resultsIn';
        await fs.mkdir(cookiesDir, { recursive: true });

        for (const group of websiteGroups) {
            processedGroups++;

            console.log(`\nProcessing group ${processedGroups}/${websiteGroups.length}: ${group.site}`);

            const cookieNames = await this.scanRelatedWebsiteGroup(group);

            if (!cookieNames) continue;
            
            results.set(group.site, cookieNames);

            // Write results to file for this group
            const websiteName = group.site.replace(/^www\./, '').replace(/\./g, '_');
            const fileName = path.join(cookiesDir, `${websiteName}_${optChoice}_cookies.txt`);
            
            try {
                await fs.writeFile(fileName, cookieNames.join('\n'), 'utf8');
                console.log(`Cookies written to ${fileName}`);
            } catch (error) {
                console.error(`Error writing to ${fileName}:`, error);
            }
        }

        return results;
    }
}

const leaderHostname = 'linux-ssh-01.ews.illinois.edu';

// Create browser instance
const cookedBrowser = await CookedBrowser.create();

const dispatchSock = new zmq.Request();
const resultSock = new zmq.Request();

dispatchSock.connect(`tcp://${leaderHostname}:56301`);
resultSock.connect(`tcp://${leaderHostname}:56302`);

while (true) {
    await dispatchSock.send('request');
    const [msg] = await dispatchSock.receive();

    const group = JSON.parse(msg.toString());
    const result = await cookedBrowser.scanRelatedWebsiteGroup(group);

    await resultSock.send(JSON.stringify({ group, result }));
}

// // Read and parse the related websites file
// const relatedWebsitesContent = await fs.readFile('./relatedwebsites.txt', 'utf8');
// const websiteGroups = relatedWebsitesContent
//     .split('\n')
//     .filter(line => line.trim().length > 0)
//     .map(line => JSON.parse(line));

// console.log(`Starting to scan ${websiteGroups.length} website groups...`);

// // Scan all website groups
// const results = await cookedBrowser.scanRelatedWebsiteGroups(websiteGroups);

// console.log('\nScan completed!');
// console.log(`Processed ${websiteGroups.length} website groups`);
// console.log(`Results saved in resultsIn/ directory`);
