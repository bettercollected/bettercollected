import React from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { Typography } from '@mui/material';
import { toast } from 'react-toastify';

import Button from '@app/components/ui/button';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';

interface ILinkViewProps {
    url: string;
    toastMessage: string;
}
export default function LinkView({ url, toastMessage }: ILinkViewProps) {
    const [_, copyToClipboard] = useCopyToClipboard();
    return (
        <>
            <div className="text-black-900 space-x-4 mt-4 underline max-w-full body4 items-center rounded p-4 flex bg-brand-100">
                <Tooltip title={url}>
                    <Typography className="truncate">{url}</Typography>
                </Tooltip>
            </div>
            <div className="flex w-full mt-4 justify-end">
                <Button
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
        </>
    );
}
