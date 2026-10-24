"use client";
import PortalFormCard from '@Components/responder-portal/portal-form-card';
import { PortalAudience, usePortalText } from '@app/lib/hooks/use-respondent-language';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { portalPath } from '@app/utils/portal-path';
import { respondentLangQuery } from '@app/utils/respondent-lang-query';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

interface FormCardsProps {
    title: string;
    /** Keep the list's heading for screen readers only (a single list needs no visible title). */
    hideTitle?: boolean;
    formsArray: Array<StandardFormDto>;
    workspace: WorkspaceDto;
    isFormCreator: boolean;
    showPinned?: boolean;
    showVisibility?: boolean;
    /** Absolute base of the public workspace (e.g. https://forms.example/acme).
     *  The relative-path fallback assumes the card renders on the client/custom
     *  domain — the admin dashboard's Public Workspace preview must link out. */
    publicBaseUrl?: string;
    audience?: PortalAudience;
}

/**
 * A list of forms on the responder portal, under an h2 (the page's h1 is the
 * workspace's name); each card's title is an h3.
 */
const FormCards = ({ title, hideTitle = false, formsArray, workspace, showPinned = true, publicBaseUrl, audience = 'respondent' }: FormCardsProps) => {
    const isCustomDomain = window?.location.host !== window.PUBLIC_CONFIG?.FORM_DOMAIN;
    const { t, language } = usePortalText(audience);
    // A ?lang= chosen on the portal carries on to the form it opens.
    const langQuery = respondentLangQuery(useSearchParams()?.get('lang'));

    if (formsArray.length === 0) return <></>;
    return (
        <section data-testid="form-cards-container">
            {!!title && <h2 lang={language} className={hideTitle ? 'sr-only' : 'text-black-800 font-semibold text-md md:text-lg mb-6'}>{title + ' (' + formsArray.length + ')'}</h2>}
            <div className="flex flex-col gap-4">
                {formsArray.map((form: StandardFormDto, idx: number) => {
                    const slug = form.settings?.customUrl;
                    const pathname = publicBaseUrl ? `${publicBaseUrl}${portalPath(null, true, 'forms', slug)}` : `${portalPath(workspace.workspaceName, isCustomDomain, 'forms', slug)}${langQuery}`;
                    return (
                        <Link
                            key={form.formId + idx}
                            href={pathname}
                            // Filling a form is a fullscreen, focused journey with no
                            // chrome back to the portal — open it in its own tab so
                            // the portal stays exactly where the responder left it.
                            target="_blank"
                            rel="noopener"
                            className="block rounded"
                        >
                            <PortalFormCard form={form} showPinned={showPinned} audience={audience} />
                            <span className="sr-only" lang={language}>
                                {t('PRIVACY.OPENS_IN_NEW_TAB')}
                            </span>
                        </Link>
                    );
                })}
            </div>
        </section>
    );
};
export default FormCards;
