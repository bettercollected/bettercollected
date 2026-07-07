"use client";
import { useTranslation } from 'next-i18next';

import { Shield as ShieldIcon } from 'lucide-react';

import { localesCommon } from '@app/constants/locales/common';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { utcToLocalDate, utcToLocalDateTIme } from '@app/utils/date-utils';
import Link from 'next/link';


interface IWorkspaceFormResponseDeletionCardProps {
    response: StandardFormResponseDto;
    deletionRequests?: boolean;
    className?: string;
    isCustomDomain?: boolean;
    workspaceName: string;
}

const DefaultDiv = (props: any) => <div {...props} />;

/**
 * A submission receipt. Its whole job is to let a responder pick THEIR
 * response out of a list — so it must carry what identifies one: the
 * submission number, the exact time, and whether it was anonymous. (It used
 * to show only the form title and a date, so three submissions to the same
 * form were indistinguishable.)
 */
export default function WorkspaceFormResponseDeletionCard({ response, deletionRequests = false, className = '', workspaceName, isCustomDomain = false }: IWorkspaceFormResponseDeletionCardProps) {
    const deletedAt = `${utcToLocalDate(response.updatedAt)}`;
    const { t } = useTranslation();

    const disabled = deletionRequests && response.status === 'success';

    const Component = disabled ? DefaultDiv : Link;

    // Link straight to the default tab: the bare id route only server-redirects
    // to /form, which showed as a URL hop + reload flicker on every open.
    const pathname = disabled ? '' : isCustomDomain ? `/submissions/${response.responseId}/form` : `/${workspaceName}/submissions/${response.responseId}/form`

    const isAnonymous = !response?.dataOwnerIdentifier;

    return (
        <Component
            href={pathname}
            className={`relative flex flex-col items-start justify-between h-full bg-white border-[1px] border-brand-100 ${disabled ? 'opacity-60 !text-black-600' : 'shadow-formCardDefault hover:border-brand-200  hover:shadow-formCard'
                } rounded ${className}`}
        >
            <div className="rounded w-full px-5 py-4 flex flex-col gap-3 items-start justify-between">
                <div className="flex w-full flex-wrap items-center justify-between gap-2">
                    <span className="text-black-800 font-medium">{response?.formTitle || t(localesCommon.untitled)}</span>
                    {response?.submissionUuid && (
                        // Mono per the design language: precise, sensitive identifiers.
                        <span className="bg-black-100 text-black-700 rounded px-2 py-0.5 font-mono text-xs" title="Your submission number — you can also search by it">
                            #{response.submissionUuid}
                        </span>
                    )}
                </div>
                <div className="text-black-600 text-sm flex items-center gap-2 flex-wrap">
                    <span>
                        {deletionRequests ? 'Requested:' : t(localesCommon.lastSubmittedAt)} {utcToLocalDateTIme(response.createdAt)}
                    </span>
                    {isAnonymous && (
                        <span className="flex items-center gap-1 rounded-full bg-[#E7F4EE] px-2 py-0.5 text-xs font-medium text-[#0E8A5F]" title="Submitted without your identity attached">
                            <ShieldIcon className="h-3 w-3" strokeWidth={2} />
                            Anonymous
                        </span>
                    )}
                    {!!response?.status && (
                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${response?.status === 'pending' ? 'bg-[#FBF3E4] text-[#B26B00]' : 'bg-black-100 text-black-600'}`}>
                            {response?.status === 'pending' ? 'Deletion requested' : `Deleted (${deletedAt})`}
                        </span>
                    )}
                </div>
            </div>
        </Component>
    );
}
