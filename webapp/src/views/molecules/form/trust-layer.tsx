'use client';

import { useEffect, useId, useRef, useState } from 'react';

import { ChevronDown, Shield } from 'lucide-react';
import { Trans } from 'react-i18next';

import useRespondentLanguage, { RESPONDENT_LANGUAGES } from '@app/lib/hooks/use-respondent-language';
import { StandardFormDto } from '@app/models/dtos/form';
import { httpUrl } from '@app/utils/http-url';
import { describeRetention, retentionExplanation } from '@app/utils/retention';

export interface TrustLayerProps {
    /** Who receives the answers: the workspace/organisation name. */
    ownerName?: string;
    /** Optional owner logo/avatar. */
    ownerImage?: string;
    /**
     * The form's settings: purpose, retention (the enforced period, with the
     * creator's explanation next to it), privacy policy link, verified
     * identity or a private form, AI insights and branding all come from here.
     */
    settings?: Partial<NonNullable<StandardFormDto['settings']>>;
    /** Where a respondent views or deletes their response (the workspace portal). */
    portalUrl?: string;
    /**
     * Show "Powered by bettercollected" as the strip's last item. Defaults to
     * the form's branding setting. The strip is the form's single footer.
     */
    poweredBy?: boolean;
    /**
     * Open the panel by default (the welcome page). Follows the prop until
     * the respondent opens or closes it themselves.
     */
    defaultExpanded?: boolean;
}

/**
 * The privacy panel on every respondent form: a quiet footer strip (who is
 * collecting, a disclosure button) that opens a short, standard panel: who
 * receives the answers, why, how long they are kept, whether a verified
 * identity is needed, whether AI is used on them, and the respondent's rights.
 * Dutch and English (`respondent` namespace), in the respondent's language.
 */
export default function TrustLayer({ ownerName, ownerImage, settings, portalUrl, poweredBy, defaultExpanded = false }: TrustLayerProps) {
    const { t, language, setLanguage } = useRespondentLanguage();
    const [expanded, setExpanded] = useState(defaultExpanded);
    const touchedRef = useRef(false);
    const toggleRef = useRef<HTMLButtonElement>(null);
    const panelId = useId();
    const toggleId = useId();

    useEffect(() => {
        if (!touchedRef.current) setExpanded(defaultExpanded);
    }, [defaultExpanded]);

    const toggle = () => {
        touchedRef.current = true;
        setExpanded((open) => !open);
    };

    const purpose = settings?.purpose?.trim();
    // Rendered as a link: http(s) only (the backend refuses anything else).
    const privacyUrl = httpUrl(settings?.privacyPolicyUrl);
    const retentionNote = retentionExplanation(settings);
    // A private form is served only to signed-in members of an admitted group.
    const signInRequired = !!(settings?.requireVerifiedIdentity || settings?.private);
    const aiUsed = !!settings?.aiInsightsEnabled;
    const aiProvider = settings?.aiInsightsProviderName?.trim();
    const showPoweredBy = poweredBy ?? !settings?.disableBranding;
    const newTab = <span className="sr-only"> {t('PRIVACY.OPENS_IN_NEW_TAB')}</span>;

    const rows: Array<{ key: string; term: string; detail: React.ReactNode }> = [];
    if (ownerName) rows.push({ key: 'receiver', term: t('PRIVACY.RECEIVER'), detail: ownerName });
    if (purpose) rows.push({ key: 'purpose', term: t('PRIVACY.PURPOSE'), detail: purpose });
    rows.push({
        key: 'retention',
        term: t('PRIVACY.RETENTION'),
        // The enforced period always; the creator's explanation next to it.
        detail: (
            <>
                {describeRetention(settings as StandardFormDto['settings'], t, language)}
                {retentionNote && (
                    <>
                        {' '}
                        <span className="text-black-600" data-testid="privacy-retention-note">
                            {retentionNote}
                        </span>
                    </>
                )}
            </>
        )
    });
    rows.push({ key: 'identity', term: t('PRIVACY.IDENTITY'), detail: signInRequired ? t('PRIVACY.IDENTITY_REQUIRED') : t('PRIVACY.IDENTITY_NOT_REQUIRED') });
    if (aiUsed) rows.push({ key: 'ai', term: t('PRIVACY.AI'), detail: aiProvider ? t('PRIVACY.AI_USED', { provider: aiProvider }) : t('PRIVACY.AI_USED_NO_PROVIDER') });
    rows.push({
        key: 'rights',
        term: t('PRIVACY.RIGHTS'),
        detail: (
            <>
                {t('PRIVACY.RIGHTS_TEXT')}{' '}
                {portalUrl && (
                    <a href={portalUrl} target="_blank" rel="noopener noreferrer" className="font-medium text-brand-600 underline underline-offset-2 hover:text-brand-700">
                        {t('PRIVACY.RIGHTS_LINK')}
                        {newTab}
                    </a>
                )}
            </>
        )
    });

    return (
        // The strip comes first in the DOM, so after the toggle the keyboard
        // moves into the panel; flex-col-reverse shows the panel above it.
        <div className="flex w-full flex-col-reverse" data-testid="privacy-panel">
            {/* 13px legible strip: who is collecting, and the way into the panel. */}
            <div className="flex w-full flex-wrap items-center justify-center gap-x-3 gap-y-1.5 border-t border-t-black-200 bg-white/90 px-4 py-2 text-[13px] backdrop-blur-sm" lang={language}>
                <Shield className="h-4 w-4 shrink-0 text-brand-500" strokeWidth={1.8} aria-hidden="true" />
                {ownerName && (
                    <span className="inline-flex items-center gap-1.5 text-black-700">
                        {ownerImage ? <img src={ownerImage} alt="" className="h-4 w-4 rounded-full object-cover" /> : null}
                        <span>
                            <Trans t={t} i18nKey="PRIVACY.COLLECTED_BY" values={{ owner: ownerName }} components={{ 1: <span className="font-semibold text-black-900" /> }} />
                        </span>
                    </span>
                )}
                {aiUsed && (
                    // The AI notice is part of what every respondent sees, not
                    // only inside the panel (#752): its own line on phones.
                    <>
                        <span className="hidden h-3 w-px bg-black-200 sm:inline-block" aria-hidden="true" />
                        <span className="w-full text-center text-black-700 sm:w-auto" data-testid="privacy-strip-ai">
                            {aiProvider ? t('PRIVACY.STRIP_AI_USED', { provider: aiProvider }) : t('PRIVACY.STRIP_AI_USED_NO_PROVIDER')}
                        </span>
                    </>
                )}
                {/* on phones the AI line ends a row: no divider starting the next */}
                <span className={`h-3 w-px bg-black-200 ${aiUsed ? 'hidden sm:inline-block' : ''}`} aria-hidden="true" />
                <button
                    ref={toggleRef}
                    id={toggleId}
                    type="button"
                    aria-expanded={expanded}
                    aria-controls={panelId}
                    onClick={toggle}
                    className="pointer-events-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-semibold text-black-900 underline decoration-dotted underline-offset-2 hover:bg-black-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                    {t('PRIVACY.TOGGLE')}
                    <ChevronDown className={`h-3.5 w-3.5 transition-transform ${expanded ? '' : 'rotate-180'}`} aria-hidden="true" />
                </button>
                {showPoweredBy && (
                    <>
                        <span className="h-3 w-px bg-black-200" aria-hidden="true" />
                        <a href="https://bettercollected.com/" target="_blank" rel="noopener noreferrer" className="pointer-events-auto text-black-600 hover:text-black-900">
                            <Trans t={t} i18nKey="PRIVACY.POWERED_BY" components={{ 1: <span className="font-semibold" /> }} />
                        </a>
                    </>
                )}
            </div>
            {expanded && (
                <section
                    id={panelId}
                    aria-labelledby={toggleId}
                    onKeyDown={(event) => {
                        if (event.key === 'Escape') {
                            touchedRef.current = true;
                            setExpanded(false);
                            toggleRef.current?.focus();
                        }
                    }}
                    className="pointer-events-auto max-h-[45vh] overflow-y-auto border-t border-t-black-200 bg-white px-4 py-4 text-[14px] leading-relaxed text-black-800 shadow-[0_-4px_16px_rgba(0,0,0,0.06)]"
                >
                    <div className="mx-auto flex max-w-[800px] flex-col gap-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                            <h2 className="text-[15px] font-semibold text-black-900">{t('PRIVACY.PANEL_LABEL')}</h2>
                            <div role="group" aria-label={t('PRIVACY.LANGUAGE')} className="flex overflow-hidden rounded-md border border-black-300 text-[12px]">
                                {RESPONDENT_LANGUAGES.map((option) => (
                                    <button
                                        key={option.code}
                                        type="button"
                                        lang={option.code}
                                        aria-pressed={language === option.code}
                                        onClick={() => setLanguage(option.code)}
                                        className={`px-2 py-1 font-medium ${language === option.code ? 'bg-black-900 text-white' : 'bg-white text-black-700 hover:bg-black-100'}`}
                                    >
                                        {option.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <dl className="grid gap-x-8 gap-y-2.5 sm:grid-cols-2" lang={language}>
                            {rows.map((row) => (
                                <div key={row.key} data-testid={`privacy-${row.key}`}>
                                    <dt className="text-[12px] font-semibold uppercase tracking-wide text-black-600">{row.term}</dt>
                                    <dd className="text-black-800">{row.detail}</dd>
                                </div>
                            ))}
                        </dl>
                        {privacyUrl && (
                            <a href={privacyUrl} target="_blank" rel="noopener noreferrer" className="w-fit font-medium text-brand-600 underline underline-offset-2 hover:text-brand-700">
                                {t('PRIVACY.POLICY_LINK')}
                                {newTab}
                            </a>
                        )}
                    </div>
                </section>
            )}
        </div>
    );
}
