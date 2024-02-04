import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';
import { useRouter } from 'next/router';

import ZeroElement from '@Components/Common/DataDisplay/Empty/ZeroElement';
import InfoIcon from '@Components/Common/Icons/FormBuilder/infoIcon';
import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import WorkspaceFormResponseDeletionCard from '@Components/WorkspaceClient/WorkspaceFormResponseDeletionCard';

import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import { formConstant } from '@app/constants/locales/form';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionsQuery, useLazyGetWorkspaceSubmissionByUUIDQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

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
        <div className="py-6 md:px-5 flex gap-6 flex-col xl:flex-row">
            {submissions?.length === 0 && (
                <ZeroElement
                    title={deletionRequests ? t(formConstant.empty.deletionRequest.title) : '0 submissions'}
                    description={deletionRequests ? t(formConstant.deletionRequestDescription) : 'Verify your email or enter your submission number you to view all your form responses.'}
                    className="!pb-[20px] w-full"
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
            <SearchBySubmissionNumber />
        </div>
    );
}

const SearchBySubmissionNumber = () => {
    const workspace = useAppSelector(selectWorkspace);
    const [submissionNumber, setSubmissionNumber] = useState('');
    const [getSubmissionByUUID, { isLoading, isError }] = useLazyGetWorkspaceSubmissionByUUIDQuery();
    const isCustomDomain = window?.location?.host !== environments.CLIENT_DOMAIN;

    const router = useRouter();
    return (
        <div className="pt-2">
            <div className="w-full flex flex-col items-center justify-center xl:w-[367px] px-6 py-8 bg-white rounded-xl">
                <Image src={'/images/search_submission.png'} height={62} width={77} />

                <div className="mt-4">
                    <div className="h4-new font-medium text-center text-new-black-800">Search by submission number</div>
                    <div className="p2-new mt-2 !text-center text-black-700">Enter your submission number to see your form response.</div>
                </div>
                <AppTextField
                    isError={isError}
                    value={submissionNumber}
                    onChange={(event) => {
                        setSubmissionNumber(event.target.value);
                    }}
                    placeholder="Enter submission number"
                    className="mt-4"
                />
                <div className="mt-2 text-xs text-red-500">
                    {isError && (
                        <div className="flex gap-2">
                            {' '}
                            <span>
                                <InfoIcon width={16} height={16} />
                            </span>
                            The submission number does not match with any form responses
                        </div>
                    )}
                </div>
                <AppButton
                    className="mt-4"
                    disabled={!submissionNumber}
                    variant={ButtonVariant.Ghost}
                    onClick={async () => {
                        if (!submissionNumber) return;
                        const response = await getSubmissionByUUID({
                            workspace_id: workspace.id,
                            submissionUUID: submissionNumber
                        });
                        if (response.data) {
                            const submissionUrl = isCustomDomain ? `/submissions/uuid/${submissionNumber}` : `/${workspace.workspaceName}/submissions/uuid/${submissionNumber}`;
                            router.push(submissionUrl);
                        }
                    }}
                >
                    Get My Submission
                </AppButton>
            </div>
        </div>
    );
};
