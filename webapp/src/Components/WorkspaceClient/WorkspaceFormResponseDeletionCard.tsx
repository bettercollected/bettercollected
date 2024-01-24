import { useTranslation } from 'next-i18next';

import { DotIcon } from '@Components/Common/Icons/Common/DotIcon';
import FormProviderIcon from '@Components/Common/Icons/Form/FormProviderIcon';
import styled from '@emotion/styled';

import ActiveLink from '@app/components/ui/links/active-link';
import { localesCommon } from '@app/constants/locales/common';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { utcToLocalDate } from '@app/utils/dateUtils';


interface IWorkspaceFormResponseDeletionCardProps {
    response: StandardFormResponseDto;
    deletionRequests?: boolean;
    className?: string;
    isCustomDomain?: boolean;
    workspaceName: string;
}

const DefaultDiv = styled.div``;

export default function WorkspaceFormResponseDeletionCard({ response, deletionRequests = false, className = '', workspaceName, isCustomDomain = false }: IWorkspaceFormResponseDeletionCardProps) {
    const submittedAt = `${utcToLocalDate(response.updatedAt)}`;
    const { t } = useTranslation();

    const disabled = deletionRequests && response.status === 'success';

    const Component = disabled ? DefaultDiv : ActiveLink;

    return (
        <Component
            href={{
                pathname: disabled ? '' : isCustomDomain ? `/submissions/${response.responseId}` : `${workspaceName}/submissions/${response.responseId}`
            }}
            className={`relative flex flex-col items-start justify-between h-full bg-white border-[1px] border-brand-100 ${
                disabled ? 'opacity-60 !text-black-600' : 'shadow-formCardDefault hover:border-brand-200  hover:shadow-formCard'
            } rounded ${className}`}
        >
            <div className="rounded w-full px-5 py-4 flex flex-col gap-4 items-start justify-between">
                <div>{response?.formTitle || t(localesCommon.untitled)}</div>
                <div className="text-black-600 text-sm flex items-center gap-2 flex-wrap">
                    <FormProviderIcon provider={response?.provider} />
                    <DotIcon />
                    <span>
                        {t(localesCommon.lastSubmittedAt)} {utcToLocalDate(response.createdAt)}
                    </span>
                    {!!response?.status && (
                        <>
                            <DotIcon />
                            <div className={`text-sm ${response?.status === 'pending' ? 'text-pink' : 'text-black-600'}`}>{response?.status === 'pending' ? 'Requested for deletion' : `Deleted (${submittedAt})`}</div>
                        </>
                    )}
                </div>
            </div>
        </Component>
    );
}