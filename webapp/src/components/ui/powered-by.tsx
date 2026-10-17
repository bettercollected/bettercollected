import React from 'react';

import Tooltip from '@app/shadcn/components/ui/tooltip';

import Logo from '@app/components/ui/logo';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

import AnchorLink from './links/anchor-link';

interface IPoweredByProps {
    isFormCreatorPortal?: boolean;
}

export default function PoweredBy({ isFormCreatorPortal }: IPoweredByProps) {
    const workspace = useAppSelector(selectWorkspace);
    const isProUser = workspace.isPro;

    const title = (
        <>
            {isProUser ? (
                <>To remove our branding Go to Form Settings</>
            ) : (
                <>
                    To remove our branding <span className=" font-semibold">Upgrade to PRO</span>
                </>
            )}
        </>
    );

    return (
        <>
            {isFormCreatorPortal ? (
                isProUser ? (
                    <ToolTipBranding title={title} />
                ) : (
                    <AnchorLink href={'/pricing-plans'} target="_blank" className="w-fit outline-hidden">
                        <ToolTipBranding title={title} />
                    </AnchorLink>
                )
            ) : (
                <div className="px-3 fixed lg:bottom-10 lg:right-20 bottom-0 right-0 left-0 lg:left-auto py-2 justify-center flex gap-2 bg-white items-center rounded border border-black-300 cursor-pointer">
                    <span className="text-black-600 text-sm leading-5">Powered by</span>
                    <Logo showProTag={false} isLink={false} isCustomDomain className="h-[14px] w-fit" />
                </div>
            )}
        </>
    );
}

const componentsProps = {
    tooltip: {
        sx: {
            padding: '8px 16px',
            fontSize: '14px',
            lineHeight: '21px',
            color: '#FFFFFF',
            backgroundColor: '#27303F',
            borderRadius: '6px',
            minWidth: '303px',
            '& .MuiTooltip-arrow': {
                color: '#27303F'
            }
        }
    }
};

const ToolTipBranding = ({ title }: { title: React.ReactNode }) => {
    return (
        <div className="px-3 fixed lg:bottom-10 lg:right-20 lg:left-auto right-0 bottom-0 left-0 justify-center py-2 flex gap-2 bg-white items-center rounded border border-black-300 cursor-pointer">
            <Tooltip label={title} side="top">
                <div className={'flex'}>
                    <span className="text-black-600 text-sm leading-5">Powered by</span>
                    <Logo showProTag={false} isLink={false} isCustomDomain className="h-[14px] w-fit" />
                </div>
            </Tooltip>
        </div>
    );
};