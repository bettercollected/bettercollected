'use client';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { selectAuth } from '@app/store/auth/slice';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responder-form-response';

/**
 * The choice to attach the signed-in respondent's email to their answers,
 * shown where they submit (the last page, or the review page). Nothing for an
 * anonymous respondent or a form that requires a verified identity (which
 * states that up front). Consent gets a calm, legible home of its own
 * (DESIGN.md §2/§4): 15px/1.5, high contrast, green-tinted container — and
 * unchecked by default, so sharing identity is a choice the person makes.
 * Named by the consent statement; the hint (whose email) describes it.
 */
export default function ShareIdentityConsent({ effectiveAnonymize }: { effectiveAnonymize: boolean }) {
    const { t } = useRespondentLanguage();
    const authState = useAppSelector(selectAuth);
    const standardForm = useAppSelector(selectResponderForm);
    const { formResponse, setFormResponse } = useFormResponse();
    if (!authState.id || standardForm?.settings?.requireVerifiedIdentity) return null;
    return (
        <label className="flex w-fit max-w-[560px] cursor-pointer flex-row items-start gap-3 rounded-[8px] border border-[#BFE0D2] bg-[#F2FAF6] p-4">
            {/* A real checkbox, not the text-field component: that one paints a
                solid white background, which hid the tick when checked. */}
            <input
                checked={!effectiveAnonymize}
                onChange={(e) => {
                    setFormResponse({
                        ...formResponse,
                        anonymize: !e.target.checked
                    });
                }}
                type="checkbox"
                aria-labelledby="share-email-consent-label"
                aria-describedby="share-email-consent-hint"
                data-testid="share-email-consent"
                className="mt-0.5 h-5 w-5 shrink-0 cursor-pointer rounded-[4px] border-2 border-control text-[#0E8A5F] checked:border-[#0E8A5F]"
            />
            <span className="flex flex-col gap-0.5">
                <span id="share-email-consent-label" className="text-[15px] leading-relaxed font-medium text-black-900">
                    {t('CONSENT.SHARE_EMAIL')}
                </span>
                <span id="share-email-consent-hint" className="text-[13px] text-black-700">
                    {t('CONSENT.SHARE_EMAIL_HINT', { email: authState?.email })}
                </span>
            </span>
        </label>
    );
}
