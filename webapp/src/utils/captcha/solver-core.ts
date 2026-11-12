import { sha256 } from '@noble/hashes/sha2.js';

/**
 * The browser's half of the automatic spam check (backend services/captcha).
 *
 * Find `SUBPUZZLES` counters `c_i` such that SHA-256 of `challenge:i:c_i` starts
 * with at least `bits - 3` zero bits: 2^bits hashes in all, expected. The hash
 * is synchronous (`@noble/hashes`, audited, MIT): `crypto.subtle.digest` is
 * asynchronous and about 14 times slower in a loop. Everything is computed in
 * memory; nothing is stored or sent anywhere but the proof itself.
 */

export const SUBPUZZLES = 8;
export const SUBPUZZLE_SHIFT = 3;

/** The challenge route's answer. */
export interface CaptchaChallenge {
    challenge: string;
    algorithm: string;
    bits: number;
    subpuzzles: number;
    expiresAt: number;
}

/** Does `digest` start with at least `bits` zero bits? */
export function hasLeadingZeroBits(digest: Uint8Array, bits: number): boolean {
    const whole = bits >> 3;
    for (let i = 0; i < whole; i++) if (digest[i] !== 0) return false;
    const rest = bits & 7;
    return rest === 0 || digest[whole] >> (8 - rest) === 0;
}

const encoder = new TextEncoder();

/** The solving state, advanced in slices so the main thread can yield between them. */
export class Solver {
    readonly counters: number[] = [];
    private readonly need: number;
    private index = 0;
    private counter = 0;
    private prefix: ReturnType<typeof sha256.create> | null = null;

    constructor(
        private readonly challenge: string,
        bits: number,
        private readonly subpuzzles: number = SUBPUZZLES,
        private readonly clock: () => number = () => performance.now()
    ) {
        this.need = bits - SUBPUZZLE_SHIFT;
    }

    get done(): boolean {
        return this.index >= this.subpuzzles;
    }

    /** Work for about `budgetMs` (all of it for `Infinity`); true once solved. */
    step(budgetMs: number): boolean {
        const started = this.clock();
        while (this.index < this.subpuzzles) {
            // the message `challenge:i:` is hashed once; each counter only adds its digits
            if (!this.prefix) this.prefix = sha256.create().update(encoder.encode(`${this.challenge}:${this.index}:`));
            for (let n = 0; n < 512; n++) {
                const digest = this.prefix.clone().update(encoder.encode(String(this.counter))).digest();
                if (hasLeadingZeroBits(digest, this.need)) {
                    this.counters.push(this.counter);
                    this.index++;
                    this.counter = 0;
                    this.prefix = null;
                    break;
                }
                this.counter++;
            }
            if (this.index < this.subpuzzles && budgetMs !== Infinity && this.clock() - started >= budgetMs) return false;
        }
        return true;
    }
}

/** The value of the `X-BC-Captcha` header. */
export const proofHeaderValue = (challenge: string, counters: number[]) => `${challenge}.${counters.join(',')}`;

export const CAPTCHA_HEADER = 'X-BC-Captcha';
