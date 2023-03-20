import React from 'react';

import Image from 'next/image';
import Link from 'next/link';

import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';

import RequestForDeletionBadge from '@app/components/badge/request-for-deletion-badge';
import { Google } from '@app/components/icons/brands/google';
import { useAppSelector } from '@app/store/hooks';
import { toMonthDateYearStr } from '@app/utils/dateUtils';

const SubmissionCard = ({ form, requestedForDeletionOnly }: any) => {
    const workspace = useAppSelector((state) => state.workspace);

    const LinkWrapper = (props: any) => {
        if (requestedForDeletionOnly) {
            return <>{props.children}</>;
        }
        return <Link {...props} />;
    };

    return (
        <LinkWrapper key={form.responseId} href={`/${workspace.workspaceName}/dashboard/submissions/${form.responseId}`}>
            <div className="flex flex-row items-center justify-between h-full gap-8 p-5 border-[1px] border-neutral-300 hover:border-blue-500 drop-shadow-sm hover:drop-shadow-lg transition cursor-pointer bg-white rounded-[20px]">
                <div className="w-full flex flex-col justify-start h-full overflow-hidden">
                    <div className="flex mb-2 w-full items-center space-x-2">
                        <div>
                            {form.provider === 'typeform' ? (
                                <div className="rounded-full border h-[24px] w-[28px] border-white relative">
                                    <Image src="/tf.png" className="rounded-full" layout="fill" alt={'T'} />
                                </div>
                            ) : (
                                <div className="rounded-full bg-white p-1">
                                    <Google />
                                </div>
                            )}
                        </div>
                        <div className="text-2xl text-grey font-bold">{!!form.dataOwnerIdentifier ? form.dataOwnerIdentifier : <p className="italic">Anonymous</p>}</div>
                    </div>
                    <div className="flex items-center mb-2"></div>
                    <div className="flex flex-col md:flex-row justify-between">
                        <div className="flex items-center">
                            <CalendarMonthIcon className="text-gray-400 text-[18px]" />
                            <div className="pl-1 text-sm italic text-gray-400">Last submitted on {!!form.updatedAt ? toMonthDateYearStr(new Date(form.updatedAt)) : 'N/A'}</div>
                        </div>
                        {form?.deletionStatus && <RequestForDeletionBadge deletionStatus={form?.deletionStatus} />}
                    </div>
                </div>
            </div>
        </LinkWrapper>
    );
};

export default SubmissionCard;
