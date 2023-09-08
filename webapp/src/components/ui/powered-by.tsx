import React from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';

import Logo from '@app/components/ui/logo';

interface IPoweredByProps {
    isFormCreatorPortal?: boolean;
}

export default function PoweredBy({ isFormCreatorPortal }: IPoweredByProps) {
    const componentsProps = {
        tooltip: {
            sx: {
                padding: '8px 16px',
                fontSize: '14px',
                lineHeight: '21px',
                color: '#FFFFFF',
                backgroundColor: '#2E2E2E',
                opacity: '0.7 !important',
                borderRadius: '4px',
                minWidth: '303px',
                '& .MuiTooltip-arrow': {
                    color: '#2E2E2E',
                    opacity: '0.7 !important'
                }
            }
        }
    };
    const title = (
        <>
            To remove our branding <span className=" font-semibold">Upgrade to PRO</span>
        </>
    );

    return (
        <>
            {isFormCreatorPortal ? (
                <Tooltip title={title} enterDelay={100} leaveDelay={100} enterTouchDelay={300} arrow placement="top" componentsProps={componentsProps}>
                    <div className="px-3 fixed bottom-4 right-12 py-2 flex gap-2 bg-white items-center rounded drop-shadow-lg">
                        <span className="body3 text-black-700">Powered by:</span>
                        <Logo showProTag={false} isFooter isCustomDomain className="h-[14px] w-fit" />
                    </div>
                </Tooltip>
            ) : (
                <div className="px-3 fixed bottom-4 right-12 py-2 flex gap-2 bg-white items-center rounded drop-shadow-lg">
                    <span className="body3 text-black-700">Powered by:</span>
                    <Logo showProTag={false} isFooter isCustomDomain className="h-[14px] w-fit" />
                </div>
            )}
        </>
    );
}
