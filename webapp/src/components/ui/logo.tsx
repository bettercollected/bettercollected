import React from 'react';

import Pro from '@Components/Common/Icons/Pro';

import AnchorLink from '@app/components/ui/links/anchor-link';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface ILogo {
    className?: string;
    showProTag?: boolean;
    [props: string]: any;
}

const Logo = ({ className, showProTag = true, ...props }: ILogo) => {
    const workspace = useAppSelector(selectWorkspace);
    const authStatus: any = useAppSelector(selectAuth);

    const user = !!authStatus ? authStatus : null;

    const isProAndIsWorkspaceAdmin = user ? user?.id === workspace?.ownerId && user?.plan === 'PRO' : false;

    return (
        <AnchorLink href={`/${workspace?.workspaceName}/dashboard`} className="w-fit outline-none" {...props}>
            <div className="flex items-center gap-2">
                <div className={`text-[20px] sm:text-[28px] font-semibold leading-8 ${className}`}>
                    <span className="text-brand-500">Better</span>
                    <span className="text-black-900">Collected.</span>
                </div>
                {isProAndIsWorkspaceAdmin && showProTag && (
                    <div className="flex items-center rounded gap-[2px] h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
                        <Pro width={12} height={12} />
                        <span className="leading-none">Pro</span>
                    </div>
                )}
            </div>
        </AnchorLink>
    );
};

Logo.defaultProps = {
    className: '',
    showProTag: true
};
export default Logo;
