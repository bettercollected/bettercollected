import React from 'react';

import { useRouter } from 'next/router';

import BetterCollectedLogo from '@Components/Common/Icons/Common/BetterCollectedLogo';
import Pro from '@Components/Common/Icons/Dashboard/Pro';

import AnchorLink from '@app/components/ui/links/anchor-link';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';


interface ILogo {
    className?: string;
    isLink?: boolean;
    showProTag?: boolean;
    isClientDomain?: boolean;
    isCustomDomain?: boolean;
    isFooter?: boolean;

    [props: string]: any;
}

const Logo = ({ className, isLink = true, isClientDomain = false, isCustomDomain = false, showProTag = true, isFooter = false, ...props }: ILogo) => {
    const workspace = useAppSelector(selectWorkspace);
    const authStatus: any = useAppSelector(selectAuth);
    const router = useRouter();
    const user = !!authStatus ? authStatus : null;
    const locale = router?.locale === 'en' ? '' : `${router?.locale}/`;
    const isProAndIsWorkspaceAdmin = user ? user?.id === workspace?.ownerId && user?.plan === 'PRO' : false;

    const customDomainUrl = isFooter ? '' : '/';
    const clientDomainUrl = `/${workspace?.workspaceName}`;
    const adminDomainUrl = `/${locale}${workspace?.workspaceName ? workspace?.workspaceName + '/' : ''}dashboard/forms`;

    const url = isCustomDomain ? customDomainUrl : isClientDomain ? clientDomainUrl : adminDomainUrl;

    const logo = (
        <div className="flex items-center gap-2 ">
            <BetterCollectedLogo className={className} />
            {isProAndIsWorkspaceAdmin && showProTag && (
                <div className="flex items-center rounded gap-[2px] h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
                    <Pro width={12} height={12} />
                    <span className="leading-none">Pro</span>
                </div>
            )}
        </div>
    );

    return isLink ? (
        <AnchorLink href={url} target={isCustomDomain && isFooter ? '_blank' : undefined} className="w-fit outline-none" {...props}>
            {logo}
        </AnchorLink>
    ) : (
        logo
    );
};

Logo.defaultProps = {
    className: '',
    showProTag: true
};
export default Logo;