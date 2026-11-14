import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CaptchaPass } from './captcha-pass';
import { CaptchaTurnedOff, MAIL_PROOF_FAILED, isMailProofFailed, mailScopeKey, resetMailProofKnowledge, sendWithMailProof } from './mail-proof';
import { CaptchaChallenge } from './solver-core';

const challenge: CaptchaChallenge = { challenge: 'c', algorithm: 'sha256-lz', bits: 14, subpuzzles: 8, expiresAt: Date.now() + 900_000 };
const fetcher = vi.fn(async () => challenge);
const refused = (code = 'captcha_missing') => ({ error: { status: 422, data: { code } } });

function makePass(proofs: string[] = ['P1', 'P2', 'P3']) {
    let n = 0;
    const solve = vi.fn(async () => proofs[n++]);
    return { pass: new CaptchaPass({ solve }), solve };
}

beforeEach(() => {
    resetMailProofKnowledge();
    fetcher.mockClear();
});

describe('sendWithMailProof', () => {
    it('sends once, without a proof, and solves nothing while the server does not ask', async () => {
        const { pass, solve } = makePass();
        const send = vi.fn(async () => ({ data: { ok: true } }));
        const answer = await sendWithMailProof({ workspaceId: 'w1' }, fetcher, send, { pass });
        expect(answer).toEqual({ data: { ok: true } });
        expect(send).toHaveBeenCalledTimes(1);
        expect(send).toHaveBeenCalledWith(undefined);
        expect(solve).not.toHaveBeenCalled();
        expect(fetcher).not.toHaveBeenCalled();
    });

    it('solves a proof and sends again, once, when the first request is refused for the spam check', async () => {
        const { pass } = makePass();
        const send = vi.fn().mockResolvedValueOnce(refused()).mockResolvedValueOnce({ data: { ok: true } });
        const answer = await sendWithMailProof({ workspaceId: 'w1' }, fetcher, send, { pass });
        expect(answer).toEqual({ data: { ok: true } });
        expect(send).toHaveBeenNthCalledWith(1, undefined);
        expect(send).toHaveBeenNthCalledWith(2, { 'X-BC-Captcha': 'P1' });
    });

    it('gives up after the second refusal and hands that answer back', async () => {
        const { pass } = makePass();
        const send = vi.fn().mockResolvedValue(refused('captcha_invalid'));
        const answer = await sendWithMailProof({ workspaceId: 'w1' }, fetcher, send, { pass });
        expect(send).toHaveBeenCalledTimes(2);
        expect(answer).toEqual(refused('captcha_invalid'));
    });

    it('solves first once the scope is known to ask, and never reuses a proof', async () => {
        const { pass } = makePass();
        const send = vi.fn().mockResolvedValueOnce(refused()).mockResolvedValue({ data: { ok: true } });
        await sendWithMailProof({ workspaceId: 'w1' }, fetcher, send, { pass });
        send.mockClear();
        await sendWithMailProof({ workspaceId: 'w1' }, fetcher, send, { pass });
        expect(send).toHaveBeenCalledTimes(1);
        expect(send).toHaveBeenCalledWith({ 'X-BC-Captcha': 'P2' });
    });

    it('does not retry a network error, a 5xx or another 422', async () => {
        for (const failure of [{ error: { status: 'FETCH_ERROR' } }, { error: { status: 503, data: { code: 'captcha_unavailable' } } }, { error: { status: 422, data: { code: 'invalid_email' } } }]) {
            const { pass } = makePass();
            const send = vi.fn().mockResolvedValue(failure);
            expect(await sendWithMailProof({ workspaceId: 'w1' }, fetcher, send, { pass })).toBe(failure);
            expect(send).toHaveBeenCalledTimes(1);
        }
    });

    it('answers with a failure of its own, and sends nothing more, when the browser cannot solve', async () => {
        const pass = new CaptchaPass({ solve: vi.fn(async () => Promise.reject(new Error('no'))) });
        const send = vi.fn().mockResolvedValue(refused());
        const answer = await sendWithMailProof({ workspaceId: 'w1' }, fetcher, send, { pass });
        expect(send).toHaveBeenCalledTimes(1);
        expect(answer).toBe(MAIL_PROOF_FAILED);
        expect(isMailProofFailed((answer as any).error)).toBe(true);
        expect(isMailProofFailed({ status: 422, data: { code: 'captcha_failed' } })).toBe(false);
    });

    it('is not stuck when the server was switched off after the page learned that it asks: it forgets, and sends once without a proof', async () => {
        const { pass } = makePass();
        const send = vi.fn().mockResolvedValueOnce(refused()).mockResolvedValue({ data: { ok: true } });
        // the page learns the server asks, solves, sends
        await sendWithMailProof({ workspaceId: 'w1' }, fetcher, send, { pass });
        send.mockClear();
        // now the challenge route answers 404 captcha_off
        const gone = vi.fn(async (): Promise<CaptchaChallenge> => {
            throw new CaptchaTurnedOff();
        });
        const answer = await sendWithMailProof({ workspaceId: 'w1' }, gone, send, { pass });
        expect(answer).toEqual({ data: { ok: true } });
        expect(send).toHaveBeenCalledTimes(1);
        expect(send).toHaveBeenCalledWith(undefined);
        // and the scope no longer asks first: the next request goes out plain
        send.mockClear();
        await sendWithMailProof({ workspaceId: 'w1' }, gone, send, { pass });
        expect(gone).toHaveBeenCalledTimes(1);
        expect(send).toHaveBeenCalledWith(undefined);
    });

    it('does not take another failure of the challenge request for the switch being off', async () => {
        const { pass } = makePass();
        const send = vi.fn().mockResolvedValue(refused());
        const broken = vi.fn(async (): Promise<CaptchaChallenge> => {
            throw new Error('network');
        });
        expect(await sendWithMailProof({ workspaceId: 'w1' }, broken, send, { pass })).toBe(MAIL_PROOF_FAILED);
        expect(send).toHaveBeenCalledTimes(1);
    });

    it('tells the scopes apart: the creator, a workspace and a form', () => {
        const keys = [{}, { workspaceId: 'w1' }, { workspaceId: 'w1', formId: 'f1' }, { workspaceId: 'w2' }].map(mailScopeKey);
        expect(new Set(keys).size).toBe(4);
    });
});
