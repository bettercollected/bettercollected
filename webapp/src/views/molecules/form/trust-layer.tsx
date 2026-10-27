'use client';

import { useId, useLayoutEffect, useRef, useState } from 'react';

import { ChevronDown, Shield } from 'lucide-react';
import { Trans } from 'react-i18next';

import useRespondentLanguage, { RESPONDENT_LANGUAGES } from '@app/lib/hooks/use-respondent-language';
import { StandardFormDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';
import { httpUrl } from '@app/utils/http-url';
import { describeRetention } from '@app/utils/retention';
import { measurePrimaryActionFit } from '@app/utils/panel-fit';
import { themeRootProps } from '@app/views/molecules/theme/theme-root';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';
import { FORM_COLUMN, FORM_GUTTER, columnPlacementClass } from '@app/views/organism/layout/form-column';

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
    /**
     * Set when the answers are also sent to a case system: the organisation
     * that runs it (the published form's `registrationDestination`). Shown as
     * text, never as markup.
     */
    registrationDestination?: { organisation?: string | null } | null;
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
    /**
     * Open by default only when the page's primary action (the welcome
     * page's Start or Verify button, `[data-primary-action]`) stays in view
     * with the panel open. Until that is measured the panel stays closed.
     */
    protectPrimaryAction?: boolean;
    /**
     * The page's layout, so the strip and panel content sit in the same
     * column as the form above them ("Left aligned" pages keep the column
     * against the left gutter).
     */
    layout?: FormSlideLayout | null;
}

/**
 * The privacy panel on every respondent form: a quiet footer strip (who is
 * collecting, a disclosure button) that opens a short, standard panel: who
 * receives the answers, why, how long they are kept, whether a verified
 * identity is needed, whether AI is used on them, and the respondent's rights.
 * Dutch and English (`respondent` namespace), in the respondent's language.
 */
const PANEL_CLASS = 'pointer-events-auto max-h-[45vh] overflow-y-auto border-t border-t-black-400 bg-white py-4 text-[14px] leading-relaxed text-black-800 shadow-[0_-4px_16px_rgba(0,0,0,0.06)]';

export default function TrustLayer({ ownerName, ownerImage, settings, registrationDestination, portalUrl, poweredBy, defaultExpanded = false, protectPrimaryAction = false, layout }: TrustLayerProps) {
    // The form's column (form-column.ts): one left and right edge from the
    // page header down to this footer.
    const column = cn(FORM_COLUMN, columnPlacementClass(layout));
    const { t, language, setLanguage } = useRespondentLanguage();
    // The Leaflet style sets the panel's terms like its margin notes
    // ("How long they are kept:") and marks the chosen language in its navy.
    const { theme } = useFormState();
    const leaflet = styleTokens(theme?.style).key === 'leaflet';
    const typeRoot = themeRootProps(theme, { typeOnly: true });
    // Keep closed until measured when the primary action is protected.
    const [actionFits, setActionFits] = useState(false);
    const openByDefault = defaultExpanded && (!protectPrimaryAction || actionFits);
    const [expanded, setExpanded] = useState(openByDefault);
    const touchedRef = useRef(false);
    const panelRef = useRef<HTMLElement>(null);
    const measureRef = useRef<HTMLElement>(null);
    const measuring = defaultExpanded && protectPrimaryAction && !touchedRef.current;
    const toggleRef = useRef<HTMLButtonElement>(null);
    const panelId = useId();
    const toggleId = useId();

    // Before paint, so a panel that may open never shows closed first.
    useLayoutEffect(() => {
        if (!touchedRef.current) setExpanded(openByDefault);
    }, [openByDefault]);

    // Measure after layout, before paint, and again whenever the page's size
    // changes: does the content up to the primary action still fit above the
    // open panel?
    useLayoutEffect(() => {
        if (!measuring) return;
        const measure = () => {
            if (touchedRef.current) return;
            const fit = measurePrimaryActionFit(document, {
                panelHeight: measureRef.current?.offsetHeight ?? 0,
                openPanelHeight: expanded ? (panelRef.current?.offsetHeight ?? 0) : 0
            });
            setActionFits(fit);
        };
        measure();
        const area = document.querySelector('[data-fit-area]');
        const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
        if (observer && area) observer.observe(area);
        const action = document.querySelector('[data-primary-action]');
        if (observer && action) observer.observe(action);
        window.addEventListener('resize', measure);
        return () => {
            observer?.disconnect();
            window.removeEventListener('resize', measure);
        };
    }, [measuring, expanded]);

    const toggle = () => {
        touchedRef.current = true;
        setExpanded((open) => !open);
    };

    const purpose = settings?.purpose?.trim();
    // Rendered as a link: http(s) only (the backend refuses anything else).
    const privacyUrl = httpUrl(settings?.privacyPolicyUrl);
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
        // One statement: the period the server enforces. Nothing the creator
        // typed is shown beside it, so the panel can't contradict itself.
        detail: describeRetention(settings as StandardFormDto['settings'], t, language, 'value')
    });
    rows.push({ key: 'identity', term: t('PRIVACY.IDENTITY'), detail: signInRequired ? t('PRIVACY.IDENTITY_REQUIRED') : t('PRIVACY.IDENTITY_NOT_REQUIRED') });
    if (aiUsed) rows.push({ key: 'ai', term: t('PRIVACY.AI'), detail: aiProvider ? t('PRIVACY.AI_USED', { provider: aiProvider }) : t('PRIVACY.AI_USED_NO_PROVIDER') });
    const destination = registrationDestination?.organisation?.trim();
    // The answers leave the form for a second place: say so, with its name.
    if (destination) rows.push({ key: 'registration', term: t('PRIVACY.REGISTRATION'), detail: t('PRIVACY.REGISTRATION_DESTINATION', { organisation: destination }) });
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

    const panelBody = (
        <div className={cn(column, 'flex flex-col gap-3')}>
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
                            className={`px-2 py-1 font-medium ${language === option.code ? (leaflet ? 'text-white' : 'bg-black-900 text-white') : 'bg-white text-black-700 hover:bg-black-100'}`}
                            style={leaflet && language === option.code ? { background: theme?.secondary } : undefined}
                        >
                            {option.label}
                        </button>
                    ))}
                </div>
            </div>
            <dl className="grid gap-x-8 gap-y-2.5 sm:grid-cols-2" lang={language}>
                {rows.map((row) => (
                    <div key={row.key} data-testid={`privacy-${row.key}`}>
                        <dt className={leaflet ? 'text-[14px] font-semibold text-black-900' : 'text-[12px] font-semibold tracking-wide text-black-600 uppercase'}>{leaflet ? `${row.term}:` : row.term}</dt>
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
    );

    return (
        // The strip comes first in the DOM, so after the toggle the keyboard
        // moves into the panel; flex-col-reverse shows the panel above it.
        // The form's faces, when its theme sets them (theme-root.ts).
        <div className="flex w-full flex-col-reverse font-form" data-testid="privacy-panel" {...typeRoot.attributes} style={typeRoot.style}>
            {/* 13px legible strip: who is collecting, and the way into the panel. */}
            <div className={cn('backdrop-blur-sm w-full border-t border-t-black-400 bg-white/90 py-2 text-[13px]', FORM_GUTTER)} lang={language}>
                {/* Items wrap freely on phones. The dividers only show from `sm`
                    up, where the strip fits on one line: a wrapped line never
                    ends (or starts) with a stray divider. */}
                <div className={cn(column, 'flex flex-wrap items-center gap-x-4 gap-y-1.5 sm:gap-x-3')}>
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
                            <span className="hidden h-3 w-px bg-black-400 sm:inline-block" aria-hidden="true" />
                            <span className="w-full text-black-700 sm:w-auto" data-testid="privacy-strip-ai">
                                {aiProvider ? t('PRIVACY.STRIP_AI_USED', { provider: aiProvider }) : t('PRIVACY.STRIP_AI_USED_NO_PROVIDER')}
                            </span>
                        </>
                    )}
                    <span className="hidden h-3 w-px bg-black-400 sm:inline-block" aria-hidden="true" />
                    <button
                        ref={toggleRef}
                        id={toggleId}
                        type="button"
                        aria-expanded={expanded}
                        aria-controls={panelId}
                        onClick={toggle}
                        // -ml-1.5: the label, not the hover padding, lines up when it starts a line.
                        className="pointer-events-auto -ml-1.5 inline-flex items-center gap-1 rounded-[4px] px-1.5 py-0.5 font-semibold text-black-900 underline decoration-dotted underline-offset-2 hover:bg-black-100 focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:outline-hidden"
                    >
                        {t('PRIVACY.TOGGLE')}
                        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${expanded ? '' : 'rotate-180'}`} aria-hidden="true" />
                    </button>
                    {showPoweredBy && (
                        <>
                            <span className="hidden h-3 w-px bg-black-400 sm:inline-block" aria-hidden="true" />
                            <a href="https://bettercollected.com/" target="_blank" rel="noopener noreferrer" className="pointer-events-auto text-black-600 hover:text-black-900">
                                <Trans t={t} i18nKey="PRIVACY.POWERED_BY" components={{ 1: <span className="font-semibold" /> }} />
                            </a>
                        </>
                    )}
                </div>
            </div>
            {/* An unseen copy of the panel, measured while the page decides whether
                it may open by default (see `protectPrimaryAction`). */}
            {measuring && (
                <section aria-hidden="true" inert ref={measureRef} className={cn(PANEL_CLASS, FORM_GUTTER)} style={{ position: 'absolute', left: 0, right: 0, bottom: 0, visibility: 'hidden', pointerEvents: 'none' }}>
                    {panelBody}
                </section>
            )}
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
                    ref={panelRef}
                    className={cn(PANEL_CLASS, FORM_GUTTER)}
                >
                    {panelBody}
                </section>
            )}
        </div>
    );
}
