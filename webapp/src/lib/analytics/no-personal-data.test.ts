import { readFileSync, readdirSync, statSync } from 'fs';
import { join } from 'path';

import { describe, expect, it } from 'vitest';

// Analytics events carry an event name only. Personal data (an email, a
// name, a user id) must never be attached as an event property.
const SRC = join(__dirname, '..', '..');
const PERSONAL_PROPERTY = /data-umami-event-(email|name|user|userid|user-id|phone)\b/i;

function sourceFiles(dir: string): string[] {
    return readdirSync(dir).flatMap((entry) => {
        const path = join(dir, entry);
        if (statSync(path).isDirectory()) return entry === 'node_modules' ? [] : sourceFiles(path);
        return /\.(tsx?|jsx?)$/.test(entry) && !entry.endsWith('.test.ts') ? [path] : [];
    });
}

describe('analytics events', () => {
    it('never carry personal data as event properties', () => {
        const offenders = sourceFiles(SRC).filter((file) => PERSONAL_PROPERTY.test(readFileSync(file, 'utf8')));
        expect(offenders).toEqual([]);
    });
});
