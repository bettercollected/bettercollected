import React from 'react';

import { useTranslation } from 'next-i18next';

import ZeroElement from '@Components/Common/DataDisplay/Empty/ZeroElement';
import WorkspaceFormResponseDeletionCard from '@Components/WorkspaceClient/WorkspaceFormResponseDeletionCard';

import EmptyFormsView from '@app/components/dashboard/empty-form';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import { formConstant } from '@app/constants/locales/form';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceSubmissionsQuery } from '@app/store/workspaces/api';

interface IWorkspaceResponsesTabContentProps {
    workspace: WorkspaceDto;
    deletionRequests?: boolean;
}

export default function WorkspaceResponsesTabContent({ workspace, deletionRequests = false }: IWorkspaceResponsesTabContentProps) {
    const { t } = useTranslation();
    const { isLoading, data, isError } = useGetWorkspaceSubmissionsQuery(
        {
            workspaceId: workspace.id,
            requestedForDeletionOly: deletionRequests
        },
        { pollingInterval: 30000 }
    );

    if (isLoading)
        return (
            <div data-testid="loader" className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Loader />
            </div>
        );

    if ((data?.items && Array.isArray(data?.items) && data?.items?.length === 0) || isError)
        return (
            <ZeroElement
                title={deletionRequests ? t(formConstant.empty.deletionRequest.title) : t(formConstant.emptyDeletionResponseTitle)}
                description={deletionRequests ? t(formConstant.deletionRequestDescription) : t(formConstant.deletionResponseDescription)}
                className="!pb-[20px]"
            />
        );

    const submissions: Array<StandardFormResponseDto> = data?.items ?? [];

    const isCustomDomain = window?.location.host !== environments.CLIENT_DOMAIN;

    const submissionCard = ({ submission }: any) => <WorkspaceFormResponseDeletionCard key={submission.responseId} response={submission} className="!bg-white" isResponderPortal />;

    return (
        <div className="py-6 px-5 lg:px-10 xl:px-20">
            {submissions?.length === 0 && <EmptyFormsView description={`0 ${t(formConstant.responses)}`} />}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6">
                {submissions?.length !== 0 &&
                    submissions?.map((submission: StandardFormResponseDto) => {
                        const slug = submission.responseId;
                        return deletionRequests ? (
                            submissionCard({ submission })
                        ) : (
                            <ActiveLink
                                key={submission.responseId}
                                href={{
                                    pathname: deletionRequests ? '' : isCustomDomain ? `/submissions/${slug}` : `${workspace.workspaceName}/submissions/${slug}`
                                }}
                            >
                                {submissionCard({ submission })}
                            </ActiveLink>
                        );
                    })}
            </div>
        </div>
    );
}
