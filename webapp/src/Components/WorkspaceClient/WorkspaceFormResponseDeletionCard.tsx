import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { Typography } from '@mui/material';

import StatusBadge from '@app/components/badge/status-badge';
import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import { formConstant } from '@app/constants/locales/form';
import { localesGlobal } from '@app/constants/locales/global';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';

interface IWorkspaceFormResponseDeletionCardProps {
    response: StandardFormResponseDto;
    isResponderPortal?: boolean;
    className?: string;
}

export default function WorkspaceFormResponseDeletionCard({ response, isResponderPortal = false, className = '' }: IWorkspaceFormResponseDeletionCardProps) {
    const submittedAt = `${toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(response.updatedAt)))}`;
    const { t } = useTranslation();
    return (
        <div className={`flex flex-col items-start justify-between h-full bg-white border-[1px] border-brand-100 ${!!response?.deletionStatus ? '' : 'hover:border-brand-500'} transition cursor-pointer rounded ${className}`}>
            <div className="rounded relative w-full px-4 py-6 flex min-h-28 flex-col gap-4 items-start justify-between">
                <div className="rounded h-[34px] w-[34px]">{response?.provider === 'typeform' ? <TypeformIcon width={34} height={34} /> : <GoogleFormIcon width={34} height={34} className="-ml-1" />}</div>
                <Tooltip title={response?.formTitle || t(localesGlobal.untitled)}>
                    <Typography className="body3 !leading-none w-[inherit]" noWrap>
                        {response?.formTitle || t(localesGlobal.untitled)}
                    </Typography>
                </Tooltip>

                <div className="w-full flex flex-col lg:flex-row justify-between">
                    <p className="body5 !text-black-700">
                        <span>
                            {t(localesGlobal.lastSubmittedAt)} {submittedAt}
                        </span>
                    </p>
                </div>

                {isResponderPortal && !!response?.deletionStatus && (
                    <Tooltip className="" title={response.deletionStatus}>
                        <StatusBadge status={response?.deletionStatus || t(formConstant.status.pending)} />
                    </Tooltip>
                )}
            </div>
        </div>
    );
}
