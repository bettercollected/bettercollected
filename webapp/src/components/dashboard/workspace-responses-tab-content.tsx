import React from 'react';

import EmptyTray from '@app/assets/svgs/empty-tray.svg';
import RequestForDeletionBadge from '@app/components/badge/request-for-deletion-badge';
import Image from '@app/components/ui/image';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { useGetWorkspaceSubmissionsQuery } from '@app/store/workspaces/api';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr } from '@app/utils/dateUtils';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IResponseCard {
    workspaceId: string;
}

export default function WorkspaceResponsesTabContent({ workspace, deletionRequests = false }: any) {
    const workspaceId = workspace.id;
    const { isLoading, data, isError } = useGetWorkspaceSubmissionsQuery(
        {
            workspaceId: workspace.id,
            requestedForDeletionOly: deletionRequests
        },
        { pollingInterval: 30000 }
    );
    const breakpoint = useBreakpoint();

    if (isLoading)
        return (
            <div data-testid="loader" className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Loader />
            </div>
        );

    if ((data?.items && Array.isArray(data?.items) && data?.items?.length === 0) || isError)
        return (
            <div data-testid="empty-forms-view" className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Image src={EmptyTray} width={40} height={40} alt="Empty Tray" />
                <p className="mt-4 p-0">0 forms</p>
            </div>
        );

    const submissions: Array<StandardFormResponseDto> = data?.items ?? [];

    const isCustomDomain = window?.location.host !== environments.CLIENT_HOST;

    const SubmissionCard = ({ submission, submittedAt }: any) => (
        <div
            className={`w-full overflow-hidden items-center justify-between h-full gap-8 p-5 border-[1px] border-neutral-300  drop-shadow-sm  ${
                !deletionRequests && 'transition cursor-pointer hover:border-blue-500 hover:drop-shadow-lg'
            }  bg-white rounded-[20px]`}
        >
            <div className="flex flex-col justify-start h-full">
                <p className="text-sm text-gray-400 italic">{['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(submission.formId, 30) : submission.formId}</p>
                <p className="text-xl text-grey mb-4 p-0">{submission.formTitle}</p>
                <div className=" w-full flex flex-col lg:flex-row justify-between">
                    <p className="text-sm text-gray-400 italic">
                        <span>Last submitted at {submittedAt}</span>
                    </p>
                    <p>{deletionRequests && submission?.deletionStatus && <RequestForDeletionBadge deletionStatus={submission?.deletionStatus} />}</p>
                </div>
            </div>
        </div>
    );
    return (
        <>
            {submissions?.length === 0 && (
                <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                    <Image src={EmptyTray} width={40} height={40} alt="Empty Tray" />
                    <p className="mt-4 p-0">0 forms</p>
                </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-6">
                {submissions?.length !== 0 &&
                    submissions?.map((submission: StandardFormResponseDto) => {
                        const slug = submission.responseId;
                        const submittedAt = `${toMonthDateYearStr(parseDateStrToDate(submission.updatedAt))} ${toHourMinStr(parseDateStrToDate(submission.updatedAt))}`;
                        return deletionRequests ? (
                            <SubmissionCard submission={submission} submittedAt={submittedAt} />
                        ) : (
                            <ActiveLink
                                key={submission.responseId}
                                href={{
                                    pathname: deletionRequests ? '' : isCustomDomain ? `/submissions/${slug}` : `${workspace.workspaceName}/submissions/${slug}`
                                }}
                            >
                                <SubmissionCard submission={submission} submittedAt={submittedAt} />
                            </ActiveLink>
                        );
                    })}
            </div>
        </>
    );
}
