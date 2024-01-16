import React from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import { Typography } from '@mui/material';
import cn from 'classnames';
import { toast } from 'react-toastify';

import { buttonConstant } from '@app/constants/locales/button';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';


interface ILinkViewProps {
    url: string;
    toastMessage: string;
    className?: string;
    buttonClassName?: string;
}

export default function LinkView({ url, toastMessage, className, buttonClassName }: ILinkViewProps) {
    const [_, copyToClipboard] = useCopyToClipboard();
    const { t } = useTranslation();
    return (
        <div className={cn('gap-2', className)}>
            <div className="text-black-900 h-[46px] space-x-4 max-w-[444px]   w-full body4 items-center rounded p-4 flex bg-brand-100">
                <Tooltip title={url}>
                    <Typography className="truncate body4 md:min-w-[200px] w-full ">{url}</Typography>
                </Tooltip>
            </div>
            <div className="flex w-full justify-end">
                <AppButton
                    size={ButtonSize.Medium}
                    onClick={() => {
                        copyToClipboard(url);
                        toast(toastMessage, {
                            type: 'info'
                        });
                    }}
                >
                    {t(buttonConstant.copyLink)}
                </AppButton>
            </div>
        </div>
    );
}