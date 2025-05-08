import * as zmq from 'zeromq';
import fs from 'fs/promises';
import path from 'path';

const optChoice = 'optIn';

// Read and parse the related websites file
const relatedWebsitesContent = await fs.readFile('./relatedwebsites.txt', 'utf8');
const websiteGroups = relatedWebsitesContent
    .split('\n')
    .filter(line => line.trim().length > 0)
    .map(line => JSON.parse(line));

console.log(`Starting to scan ${websiteGroups.length} website groups...`);

const cookiesDir = 'resultsIn';
await fs.mkdir(cookiesDir, { recursive: true });

const dispatchSock = new zmq.Reply();
dispatchSock.bindSync('tcp://*:56301');

(async () => {
    let processedGroups = 0;

    for await (const [msg] of dispatchSock) {
        console.log(`Processing group ${processedGroups}/${websiteGroups.length}: ${websiteGroups[processedGroups].site}`);

        const group = websiteGroups[processedGroups++];

        await dispatchSock.send(JSON.stringify({ group, cookiesDir }));

        if (processedGroups >= websiteGroups.length) break;
    }
})();
