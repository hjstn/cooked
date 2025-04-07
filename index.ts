import puppeteer from 'puppeteer';
import { WebsiteCrawler } from './lib/WebsiteCrawler.ts';

const browser = await puppeteer.launch({ headless: false });

const [page] = await browser.pages();

const crawler = new WebsiteCrawler(page, 'https://adv-sec-sp25.nikita.phd/');

const links = await crawler.getInternalLinks(20);
console.log(Array.from(links));

await browser.close();
