import React from 'react';

import { useTranslation } from 'next-i18next';

import ZeroElement from '@Components/Common/DataDisplay/Empty/ZeroElement';
import SearchByUUIDWrapper from '@Components/RespondersPortal/SearchByUUIDWrapper';
import WorkspaceFormResponseDeletionCard from '@Components/WorkspaceClient/WorkspaceFormResponseDeletionCard';

import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import { formConstant } from '@app/constants/locales/form';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
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

    const isCustomDomain = window?.location.host !== environments.CLIENT_DOMAIN;

    return (
        <SearchByUUIDWrapper>
            {submissions?.length === 0 && (
                <ZeroElement
                    title={deletionRequests ? t(formConstant.empty.deletionRequest.title) : '0 submissions'}
                    description={deletionRequests ? t(formConstant.deletionRequestDescription) : 'Verify your email or enter your submission number you to view all your form responses.'}
                    className="!pb-[20px]"
                />
            )}

            {submissions?.length !== 0 && (
                <div className="w-full">
                    <div className=" flex flex-col w-full gap-4 ">
                        {submissions?.map((submission: StandardFormResponseDto) => (
                            <WorkspaceFormResponseDeletionCard deletionRequests={deletionRequests} key={submission.responseId} response={submission} isCustomDomain={isCustomDomain} workspaceName={workspace.workspaceName} />
                        ))}
                    </div>
                </div>
            )}
        </SearchByUUIDWrapper>
    );
}
