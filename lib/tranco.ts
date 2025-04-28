import fs from 'fs';
import * as csv from 'fast-csv';

export interface TrancoEntry {
    rank: number;
    site: string;
}

export function parseTranco(filename: string): Promise<TrancoEntry[]> {
    return new Promise((resolve, reject) => {
        const results: TrancoEntry[] = [];

        fs.createReadStream(filename, { encoding: 'utf-8' })
        .pipe(csv.parse<TrancoEntry, TrancoEntry>({ headers: true }))
        .on('data', row => results.push({ rank: Number(row.rank), site: row.site }))
        .on('error', error => reject(error))
        .on('end', () => resolve(results));
    });
}
