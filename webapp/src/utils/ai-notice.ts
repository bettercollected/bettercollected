import { StandardFormDto } from '@app/models/dtos/form';

/**
 * The AI notice token to send back with a submission (#752), or null.
 *
 * The backend hands one out with the published form while the form allows AI
 * insights; the privacy panel (trust-layer.tsx) shows its AI row under the
 * same condition (`settings.aiInsightsEnabled`). The token goes back only when
 * this page shows that row, so a response is marked as having seen the notice
 * only when the notice was part of the page. Without it the response is
 * stored as usual and never analysed.
 */
export function aiNoticeTokenToSend(form?: Partial<StandardFormDto> | null): string | null {
    if (!form?.settings?.aiInsightsEnabled) return null;
    const token = form.aiNoticeToken;
    return typeof token === 'string' && token.length > 0 ? token : null;
}
