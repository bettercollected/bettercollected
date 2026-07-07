
"use client";
import { useTranslation } from 'next-i18next';
import { usePathname, useRouter } from 'next/navigation';

import ZeroElement from '@Components/common/zero-elament';
import { Button } from '@app/shadcn/components/ui/button';
import WorkspaceFormResponseDeletionCard from '@Components/workspace-client/workspace-form-response-deletion-card';

import Loader from '@app/components/ui/loader';
import { formConstant } from '@app/constants/locales/form';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionsQuery } from '@app/store/workspaces/api';

interface IWorkspaceResponsesTabContentProps {
    workspace: WorkspaceDto;
    deletionRequests?: boolean;
}

export default function WorkspaceResponsesTabContent({ workspace, deletionRequests = false }: IWorkspaceResponsesTabContentProps) {
    const { t } = useTranslation();
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

    const getEmptyMessage = () => {
        if (deletionRequests) return t(formConstant.deletionRequestDescription);
        return "You haven't submitted any responses to this workspace's forms yet.";
    };

    const handleVerify = () => {
        const params = new URLSearchParams({
            type: 'responder',
            workspace_id: workspace.id,
            redirect_to: pathname ?? ''
        });
        router.push(`/login?${params.toString()}`);
    };

    return (
        <>
            {/* Signed out we DON'T know there are no submissions — "No submissions
                yet" would be a false claim to a responder with ten of them. Say
                what's actually true: verify (or use a receipt number) to see them. */}
            {submissions?.length === 0 && !auth.id && (
                <div className="px-13 flex h-full min-h-[290px] w-full flex-col items-center justify-center gap-4 rounded-xl bg-white py-[60px] text-center">
                    <div>
                        <h1 className="h4-new mt-2">Find your submissions</h1>
                        <p className="p2-new !text-black-700 mt-1 max-w-[290px] md:max-w-[360px]">Verify your email to see responses you&apos;ve submitted, or enter a submission number in the search panel.</p>
                    </div>
                    <Button size="sm" onClick={handleVerify}>
                        Verify email
                    </Button>
                    <p className="text-black-500 max-w-[360px] text-xs">Submitted anonymously? Your submission number is the only way to find that response — that&apos;s what keeps it anonymous.</p>
                </div>
            )}
            {submissions?.length === 0 && !!auth.id && <ZeroElement title={deletionRequests ? t(formConstant.empty.deletionRequest.title) : 'No submissions yet'} description={getEmptyMessage()} className="!pb-[20px]" />}

            {submissions?.length !== 0 && (
                <div className="w-full">
                    <div className=" flex flex-col w-full gap-4 ">
                        {submissions?.map((submission: StandardFormResponseDto) => (
                            <WorkspaceFormResponseDeletionCard deletionRequests={deletionRequests} key={submission.responseId} response={submission} isCustomDomain={isCustomDomain} workspaceName={workspace.workspaceName} />
                        ))}
                    </div>
                    {!deletionRequests && (
                        <p className="text-black-600 mt-4 text-xs">
                            Anonymous submissions aren&apos;t linked to your account — find them with their submission number. That&apos;s what keeps them anonymous.
                        </p>
                    )}
                </div>
            )}
        </>
    );
}
