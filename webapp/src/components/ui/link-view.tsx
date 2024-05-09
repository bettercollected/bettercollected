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
    return (
        <div className={cn('gap-2', className)}>
            <div className="text-black-900 body4 bg-brand-100 flex   h-[46px] w-full max-w-[444px] items-center space-x-4 rounded p-4">
                <Tooltip title={url}>
                    <Typography className="body4 w-full truncate md:min-w-[200px] ">{url}</Typography>
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
                    {'Copy Link'}
                </AppButton>
            </div>
        </div>
    );
}
