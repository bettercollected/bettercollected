
"use client";
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import Link from 'next/link';

interface FormCardsProps {
    title: string;
    formsArray: Array<StandardFormDto>;
    workspace: WorkspaceDto;
    isFormCreator: boolean;
    showPinned?: boolean;
    showVisibility?: boolean;
    /** Absolute base of the public workspace (e.g. https://forms.example/acme).
     *  The relative-path fallback assumes the card renders on the client/custom
     *  domain — the admin dashboard's Public Workspace preview must link out. */
    publicBaseUrl?: string;
}

const FormCards = ({ title, formsArray, workspace, showPinned = true, showVisibility, publicBaseUrl }: FormCardsProps) => {
    const isCustomDomain = window?.location.host !== window.PUBLIC_CONFIG?.FORM_DOMAIN;

    if (formsArray.length === 0) return <></>;
    return (
        <div data-testid="form-cards-container">
            {!!title && <h1 className="text-black-800 font-semibold text-md md:text-lg mb-6">{title + ' (' + formsArray.length + ')'}</h1>}
            <div className="flex flex-col gap-4">
                {formsArray.map((form: StandardFormDto, idx: number) => {
                    const slug = form.settings?.customUrl;
                    const pathname = publicBaseUrl ? `${publicBaseUrl}/forms/${slug}` : isCustomDomain ? `/forms/${slug}` : `/${workspace.workspaceName}/forms/${slug}`;
                    return (
                        <Link
                            key={form.formId + idx}
                            href={pathname}
                            // Filling a form is a fullscreen, focused journey with no
                            // chrome back to the portal — open it in its own tab so
                            // the portal stays exactly where the responder left it.
                            target="_blank"
                            rel="noopener"
                        >
                            <WorkspaceFormCard isResponderPortal showVisibility={showVisibility} showPinned={showPinned} form={form} hasCustomDomain={isCustomDomain} workspace={workspace} />
                        </Link>
                    );
                })}
            </div>
        </div>
    );
};
export default FormCards;