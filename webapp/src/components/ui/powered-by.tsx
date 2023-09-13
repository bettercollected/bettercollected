import React from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';

import Logo from '@app/components/ui/logo';

import AnchorLink from './links/anchor-link';

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
                borderRadius: '4px',
                minWidth: '303px',
                '& .MuiTooltip-arrow': {
                    color: '#2E2E2E'
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
                <AnchorLink href={'/pricing-plans'} target="_blank" className="w-fit outline-none">
                    <Tooltip title={title} enterDelay={100} leaveDelay={100} enterTouchDelay={300} arrow placement="top" componentsProps={componentsProps}>
                        <div className="px-3 fixed bottom-10 right-20 py-2 flex gap-2 bg-white items-center rounded shadow-hover cursor-pointer">
                            <span className="body3 text-black-700">Powered by:</span>
                            <Logo showProTag={false} isLink={false} isCustomDomain className="h-[14px] w-fit" />
                        </div>
                    </Tooltip>
                </AnchorLink>
            ) : (
                <AnchorLink href={'/pricing-plans'} target="_blank" className="w-fit outline-none">
                    <div className="px-3 fixed bottom-10 right-20 py-2 flex gap-2 bg-white items-center rounded shadow-hover cursor-pointer">
                        <span className="body3 text-black-700">Powered by:</span>
                        <Logo showProTag={false} isLink={false} isCustomDomain className="h-[14px] w-fit" />
                    </div>
                </AnchorLink>
            )}
        </>
    );
}
