import React from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { Typography } from '@mui/material';
import cn from 'classnames';
import { toast } from 'react-toastify';

import Button from '@app/components/ui/button';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';

type SizeNames = 'large' | 'medium' | 'small' | 'extraSmall';
interface ILinkViewProps {
    url: string;
    toastMessage: string;
    className?: any;
    buttonSize?: SizeNames;
}
export default function LinkView({ url, toastMessage, className, buttonSize = 'small' }: ILinkViewProps) {
    const [_, copyToClipboard] = useCopyToClipboard();
    return (
        <div className={className}>
            <div className="text-black-900 h-[46px] space-x-4   w-full body4 items-center rounded p-4 flex bg-brand-100">
                <Tooltip title={url}>
                    <Typography className="truncate">{url}</Typography>
                </Tooltip>
            </div>
            <div className="flex w-full justify-end">
                <Button
                    size={buttonSize}
                    variant="outline"
                    onClick={() => {
                        copyToClipboard(url);
                        toast(toastMessage, {
                            type: 'info'
                        });
                    }}
                >
                    Copy Link
                </Button>
            </div>
        </div>
    );
}
