import React from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';

import ZeroElement from '@Components/Common/DataDisplay/Empty/ZeroElement';
import AppTextField from '@Components/Common/Input/AppTextField';
import WorkspaceFormResponseDeletionCard from '@Components/WorkspaceClient/WorkspaceFormResponseDeletionCard';

import EmptyFormsView from '@app/components/dashboard/empty-form';
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
    const { isLoading, data, isError } = useGetWorkspaceSubmissionsQuery(
        {
            workspaceId: workspace.id,
            requestedForDeletionOly: deletionRequests
        },
        { pollingInterval: 30000, skip: !auth.id }
    );

    if (auth.id && isLoading)
        return (
            <div data-testid="loader" className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Loader />
            </div>
        );

    if ((data?.items && Array.isArray(data?.items) && data?.items?.length === 0) || isError || !auth.id)
        return (
            <ZeroElement
                title={deletionRequests ? t(formConstant.empty.deletionRequest.title) : t(formConstant.emptyDeletionResponseTitle)}
                description={deletionRequests ? t(formConstant.deletionRequestDescription) : t(formConstant.deletionResponseDescription)}
                className="!pb-[20px]"
            />
        );

    const submissions: Array<StandardFormResponseDto> = data?.items ?? [];

    const isCustomDomain = window?.location.host !== environments.CLIENT_DOMAIN;

    return (
        <div className="py-6 px-5 flex gap-6 flex-col-reverse md:flex-row">
            {submissions?.length === 0 && <EmptyFormsView description={`0 ${t(formConstant.responses)}`} />}
            <div className=" flex flex-col w-full gap-4">
                {submissions?.length !== 0 &&
                    submissions?.map((submission: StandardFormResponseDto) => {
                        return <WorkspaceFormResponseDeletionCard deletionRequests={deletionRequests} key={submission.responseId} response={submission} isCustomDomain={isCustomDomain} workspaceName={workspace.workspaceName} />;
                    })}
            </div>
            <SearchBySubmissionNumber />
        </div>
    );
}

const SearchBySubmissionNumber = () => {
    return (
        <div className="pt-2">
            <div className="w-full flex flex-col items-center justify-center md:w-[367px] px-6 py-8 bg-white rounded-xl">
                <Image src={'/images/search_submission.png'} height={62} width={77} />

                <div className="mt-4">
                    <div className="h4-new font-medium text-center text-new-black-800">Search by submission number</div>
                    <div className="p2-new mt-2 !text-center text-black-700">Enter your submission number to see your form response.</div>
                </div>
                <AppTextField placeholder="Enter your submission number here" className="mt-4" />
            </div>
        </div>
    );
};
