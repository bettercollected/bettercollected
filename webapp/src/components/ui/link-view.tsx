import React from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { Typography } from '@mui/material';
import cn from 'classnames';
import { toast } from 'react-toastify';

import Button from '@app/components/ui/button';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';

type SizeNames = 'large' | 'medium' | 'small' | 'extraSmall';
type VariantNames = 'ghost' | 'solid' | 'transparent' | 'outline';
interface ILinkViewProps {
    url: string;
    toastMessage: string;
    className?: any;
    buttonSize?: SizeNames;
    buttonVarient?: VariantNames;
}
export default function LinkView({ url, toastMessage, className, buttonSize = 'small', buttonVarient = 'outline' }: ILinkViewProps) {
    const [_, copyToClipboard] = useCopyToClipboard();
    return (
        <div className={cn('gap-2', className)}>
            <div className="text-black-900 h-[46px] space-x-4 max-w-[444px]   w-full body4 items-center rounded p-4 flex bg-brand-100">
                <Tooltip title={url}>
                    <Typography className="truncate">{url}</Typography>
                </Tooltip>
            </div>
            <div className="flex w-full justify-end">
                <Button
                    size={buttonSize}
                    variant={buttonVarient}
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
