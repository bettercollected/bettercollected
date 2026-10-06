import { describe, expect, it } from 'vitest';

import { aiNoticeTokenToSend } from './ai-notice';

const form = (settings: Record<string, unknown> | undefined, aiNoticeToken?: string | null) => ({ settings, aiNoticeToken }) as any;

describe('aiNoticeTokenToSend — #752', () => {
    it('sends the token while the page shows the AI notice', () => {
        expect(aiNoticeTokenToSend(form({ aiInsightsEnabled: true, aiInsightsProviderName: 'OpenAI' }, 'v1.abc.def'))).toBe('v1.abc.def');
    });

    it('never sends one when the page shows no AI notice', () => {
        expect(aiNoticeTokenToSend(form({ aiInsightsEnabled: false }, 'v1.abc.def'))).toBeNull();
        expect(aiNoticeTokenToSend(form(undefined, 'v1.abc.def'))).toBeNull();
    });

    it('sends nothing without a token', () => {
        expect(aiNoticeTokenToSend(form({ aiInsightsEnabled: true }, null))).toBeNull();
        expect(aiNoticeTokenToSend(form({ aiInsightsEnabled: true }, ''))).toBeNull();
        expect(aiNoticeTokenToSend(null)).toBeNull();
    });
});
