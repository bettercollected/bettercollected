// The proofs of one form in memory: solved after the first interaction, single
// use, the next one right after each, a stale one replaced, and a refused one
// replaced by a fresh challenge.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CaptchaPass, REFRESH_AFTER_MS, SLOW_AFTER_MS } from './captcha-pass';
import { CaptchaUnavailable } from './solve';

const challenge = (n: number) => ({ challenge: `c${n}`, algorithm: 'sha256-lz', bits: 14, subpuzzles: 8, expiresAt: 0 });

function setup() {
    let issued = 0;
    const clock = { now: 1_000_000 };
    const fetcher = vi.fn(async () => challenge(++issued));
    const solve = vi.fn(async (c: { challenge: string }) => `proof-of-${c.challenge}`);
    const pass = new CaptchaPass({ solve, now: () => clock.now });
    return { pass, fetcher, solve, clock };
}
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('the proofs of a form', () => {
    beforeEach(() => vi.useRealTimers());

    it('solves nothing until asked, then once, whatever the number of interactions', async () => {
        const { pass, fetcher } = setup();
        expect(fetcher).not.toHaveBeenCalled();
        pass.warm(fetcher);
        pass.warm(fetcher);
        await settle();
        expect(fetcher).toHaveBeenCalledTimes(1);
        expect(pass.busy).toBe(true);
    });

    it('hands out a finished proof once and starts the next straight after', async () => {
        const { pass, fetcher } = setup();
        pass.warm(fetcher);
        await settle();
        expect(await pass.take(fetcher)).toBe('proof-of-c1');
        await settle();
        expect(fetcher).toHaveBeenCalledTimes(2);
        // a second take gets the next one, never the spent one
        expect(await pass.take(fetcher)).toBe('proof-of-c2');
    });

    it('solves on the spot when nothing was started, and waits for one on its way', async () => {
        const { pass, fetcher } = setup();
        expect(await pass.take(fetcher)).toBe('proof-of-c1');
        const second = pass.take(fetcher);
        const third = pass.take(fetcher);
        const proofs = [await second, await third];
        expect(new Set(proofs).size).toBe(2);
    });

    it('replaces a proof that is 12 minutes old', async () => {
        const { pass, fetcher, clock } = setup();
        pass.warm(fetcher);
        await settle();
        clock.now += REFRESH_AFTER_MS + 1;
        expect(await pass.take(fetcher)).not.toBe('proof-of-c1');
        expect(fetcher.mock.calls.length).toBeGreaterThanOrEqual(2);
    });

    it('re-solves in the background when an unused proof reaches that age', async () => {
        vi.useFakeTimers();
        const { pass, fetcher } = setup();
        pass.warm(fetcher);
        await vi.advanceTimersByTimeAsync(10);
        expect(fetcher).toHaveBeenCalledTimes(1);
        await vi.advanceTimersByTimeAsync(REFRESH_AFTER_MS + 10);
        expect(fetcher).toHaveBeenCalledTimes(2);
    });

    it('drops what is held for a fresh challenge when asked (a refused proof, a network that changed)', async () => {
        const { pass, fetcher } = setup();
        pass.warm(fetcher);
        await settle();
        const fresh = await pass.take(fetcher, { fresh: true });
        expect(fresh).toBe('proof-of-c2');
    });

    it('says when the wait is slow (1.5 s) and when it ends', async () => {
        vi.useFakeTimers();
        const onSlow = vi.fn();
        const onDone = vi.fn();
        let release!: (value: string) => void;
        const solve = vi.fn(() => new Promise<string>((resolve) => (release = resolve)));
        const pass = new CaptchaPass({ solve });
        const fetcher = vi.fn(async () => challenge(1));
        const taken = pass.take(fetcher, { onSlow, onDone });
        await vi.advanceTimersByTimeAsync(SLOW_AFTER_MS - 100);
        expect(onSlow).not.toHaveBeenCalled();
        await vi.advanceTimersByTimeAsync(200);
        expect(onSlow).toHaveBeenCalledTimes(1);
        expect(onDone).not.toHaveBeenCalled();
        release('late');
        expect(await taken).toBe('late');
        expect(onDone).toHaveBeenCalledTimes(1);
    });

    it('stays silent for a proof that is ready', async () => {
        const { pass, fetcher } = setup();
        pass.warm(fetcher);
        await settle();
        const onSlow = vi.fn();
        await pass.take(fetcher, { onSlow });
        expect(onSlow).not.toHaveBeenCalled();
        expect(SLOW_AFTER_MS).toBe(1500);
    });

    it('rejects with CaptchaUnavailable when the challenge cannot be had or solved, and tries again next time', async () => {
        const solve = vi.fn().mockRejectedValueOnce(new CaptchaUnavailable()).mockResolvedValue('ok');
        const pass = new CaptchaPass({ solve });
        const fetcher = vi.fn(async () => challenge(1));
        await expect(pass.take(fetcher)).rejects.toBeInstanceOf(CaptchaUnavailable);
        const broken = vi.fn().mockRejectedValue(new Error('network'));
        await expect(pass.take(broken)).rejects.toBeInstanceOf(CaptchaUnavailable);
        expect(await pass.take(fetcher)).toBe('ok');
    });

    it('a warm-up that fails is silent', async () => {
        const pass = new CaptchaPass({ solve: async () => 'x' });
        pass.warm(async () => {
            throw new Error('offline');
        });
        await settle();
        expect(pass.busy).toBe(false);
    });
});
