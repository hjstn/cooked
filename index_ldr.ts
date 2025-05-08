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

let processedGroups = 0;

const cookiesDir = 'resultsIn';
await fs.mkdir(cookiesDir, { recursive: true });

const dispatchSock = new zmq.Push();
const resultSock = new zmq.Reply();

dispatchSock.bindSync('tcp://*:56301');
resultSock.bindSync('tcp://*:56302');

(async () => {
    for await (const [msg] of resultSock) {
        const { group, result } = JSON.parse(msg.toString());

        if (!result) {
            console.log(`No result for ${group.site}, skipping`);
            continue;
        };

        // Write results to file for this group
        const websiteName = group.site.replace(/^www\./, '').replace(/\./g, '_');
        const fileName = path.join(cookiesDir, `${websiteName}_${optChoice}_cookies.txt`);
        
        try {
            await fs.writeFile(fileName, result.join('\n'), 'utf8');
            console.log(`Cookies written to ${fileName}`);
        } catch (error) {
            console.error(`Error writing to ${fileName}:`, error);
        }
    }
})();

for (const group of websiteGroups) {
    processedGroups++;

    console.log(`\nProcessing group ${processedGroups}/${websiteGroups.length}: ${group.site}`);

    await dispatchSock.send(JSON.stringify(group));
}