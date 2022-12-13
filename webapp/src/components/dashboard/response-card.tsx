import React from 'react';

import EmptyTray from '@app/assets/svgs/empty-tray.svg';
import Image from '@app/components/ui/image';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { useGetWorkspaceSubmissionsQuery } from '@app/store/workspaces/api';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr } from '@app/utils/dateUtils';

interface IResponseCard {
    workspaceId: string;
}

export default function ResponseCard({ workspaceId }: IResponseCard) {
    const { isLoading, data, isError } = useGetWorkspaceSubmissionsQuery(workspaceId, { pollingInterval: 30000 });

    if (isLoading)
        return (
            <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Loader />
            </div>
        );

    if ((data?.payload?.content && Array.isArray(data?.payload?.content) && data?.payload?.content?.length === 0) || isError)
        return (
            <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Image src={EmptyTray} width={40} height={40} alt="Empty Tray" />
                <p className="mt-4 p-0">0 forms</p>
            </div>
        );

    const submissions: Array<StandardFormResponseDto> = data?.payload?.content ?? [];

    return (
        <>
            <div className="pt-3 md:pt-7">
                {submissions?.length === 0 && (
                    <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                        <Image src={EmptyTray} width={40} height={40} alt="Empty Tray" />
                        <p className="mt-4 p-0">0 forms</p>
                    </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">
                    {submissions?.length !== 0 &&
                        submissions?.map((submission: StandardFormResponseDto) => {
                            const slug = submission.responseId;
                            const submittedAt = `${toMonthDateYearStr(parseDateStrToDate(submission.updatedAt))} ${toHourMinStr(parseDateStrToDate(submission.updatedAt))}`;
                            return (
                                <ActiveLink
                                    key={submission.responseId}
                                    href={{
                                        pathname: `/submissions/[slug]?workspaceId=${workspaceId}`,
                                        query: { slug, workspaceId }
                                    }}
                                >
                                    <div className="flex flex-row items-center justify-between h-full gap-8 p-5 border-[1px] border-neutral-300 hover:border-blue-500 drop-shadow-sm hover:drop-shadow-lg transition cursor-pointer bg-white rounded-[20px]">
                                        <div className="flex flex-col justify-start h-full">
                                            <p className="text-sm text-gray-400 italic">{submission.formId}</p>
                                            <p className="text-xl text-grey mb-4 p-0">{submission.formTitle}</p>
                                            <p className="text-sm text-gray-400 italic">
                                                <span>Last submitted at {submittedAt}</span>
                                            </p>
                                        </div>
                                    </div>
                                </ActiveLink>
                            );
                        })}
                </div>
            </div>
        </>
    );
}
