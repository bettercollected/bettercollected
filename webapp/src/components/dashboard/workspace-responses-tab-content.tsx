"use client";
import { usePathname, useRouter } from 'next/navigation';

import ZeroElement from '@Components/common/zero-elament';
import { Button } from '@app/shadcn/components/ui/button';
import WorkspaceFormResponseDeletionCard from '@Components/workspace-client/workspace-form-response-deletion-card';

import Loader from '@app/components/ui/loader';
import { PortalAudience, usePortalText } from '@app/lib/hooks/use-respondent-language';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionsQuery } from '@app/store/workspaces/api';

interface IWorkspaceResponsesTabContentProps {
    workspace: WorkspaceDto;
    deletionRequests?: boolean;
    /** In the respondent's language on the portal, in the app's on the team's dashboard. */
    audience?: PortalAudience;
}

/**
 * "My submissions" and "Deletion requests" on the responder portal. The
 * page's h1 is the workspace's name; this tab's content sits under an h2
 * (visible only when there is nothing to list), and each receipt card's form
 * title is an h3.
 */
export default function WorkspaceResponsesTabContent({ workspace, deletionRequests = false, audience = 'team' }: IWorkspaceResponsesTabContentProps) {
    const { t, language } = usePortalText(audience);
    const auth = useAppSelector(selectAuth);
    const router = useRouter();
    const pathname = usePathname();
    const { isLoading, data } = useGetWorkspaceSubmissionsQuery(
        {
            workspaceId: workspace.id,
            requestedForDeletionOly: deletionRequests
        },
        { pollingInterval: 30000, skip: !auth.id }
    );

    if (auth.isLoading || isLoading)
        return (
            <div data-testid="loader" className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Loader />
            </div>
        );

    const submissions: Array<StandardFormResponseDto> = data?.items ?? [];

    const isCustomDomain = window?.location.host !== window.PUBLIC_CONFIG?.FORM_DOMAIN;

    const handleVerify = () => {
        const params = new URLSearchParams({
            type: 'responder',
            workspace_id: workspace.id,
            redirect_to: pathname ?? ''
        });
        router.push(`/login?${params.toString()}`);
    };

    return (
        <div lang={language}>
            {/* Signed out we DON'T know there are no submissions — "No submissions
                yet" would be a false claim to a responder with ten of them. Say
                what's actually true: verify (or use a receipt number) to see them. */}
            {submissions?.length === 0 && !auth.id && (
                <div className="px-13 flex h-full min-h-[290px] w-full flex-col items-center justify-center gap-4 rounded bg-white py-[60px] text-center">
                    <div>
                        <h2 className="h4-new mt-2">{t('SUBMISSIONS.FIND_TITLE')}</h2>
                        <p className="p2-new text-black-700! mt-1 max-w-[290px] md:max-w-[360px]">{t('SUBMISSIONS.FIND_TEXT')}</p>
                    </div>
                    <Button size="sm" onClick={handleVerify}>
                        {t('PORTAL.VERIFY_EMAIL')}
                    </Button>
                    <p className="text-black-600 max-w-[360px] text-xs">{t('SUBMISSIONS.FIND_ANONYMOUS')}</p>
                </div>
            )}
            {submissions?.length === 0 && !!auth.id && (
                <ZeroElement
                    title={deletionRequests ? t('SUBMISSIONS.NO_REQUESTS_TITLE') : t('SUBMISSIONS.EMPTY_TITLE')}
                    description={deletionRequests ? t('SUBMISSIONS.NO_REQUESTS_TEXT') : t('SUBMISSIONS.EMPTY_TEXT')}
                    className="pb-[20px]!"
                    headingLevel={2}
                />
            )}

            {submissions?.length !== 0 && (
                <section className="w-full">
                    <h2 className="sr-only">{deletionRequests ? t('PORTAL.DELETION_REQUESTS') : t('PORTAL.MY_SUBMISSIONS')}</h2>
                    <div className=" flex flex-col w-full gap-4 ">
                        {submissions?.map((submission: StandardFormResponseDto) => (
                            <WorkspaceFormResponseDeletionCard deletionRequests={deletionRequests} key={submission.responseId} response={submission} isCustomDomain={isCustomDomain} workspaceName={workspace.workspaceName} audience={audience} />
                        ))}
                    </div>
                    {!deletionRequests && <p className="text-black-600 mt-4 text-xs">{t('SUBMISSIONS.ANONYMOUS_NOTE')}</p>}
                </section>
            )}
        </div>
    );
}
