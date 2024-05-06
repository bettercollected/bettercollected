import NewLogo from '@app/assets/images/new_logo.png';
import Image from 'next/image';

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
    const user = !!authStatus ? authStatus : null;
    const isProAndIsWorkspaceAdmin = user ? user?.id === workspace?.ownerId && user?.plan === 'PRO' : false;

    const customDomainUrl = isFooter ? '' : '/';
    const clientDomainUrl = `/${workspace?.workspaceName}`;
    const adminDomainUrl = `/${workspace?.workspaceName ? workspace?.workspaceName + '/' : ''}dashboard/forms`;

    const url = isCustomDomain ? customDomainUrl : isClientDomain ? clientDomainUrl : adminDomainUrl;

    const logo = (
        <div className="flex items-center gap-2 ">
            {/* <BetterCollectedLogo className={className} /> */}
            <Image src={NewLogo} alt="new-logo" width={185} height={19} priority />
            {isProAndIsWorkspaceAdmin && showProTag && (
                <ProLogo />
                // <div className="sm:body5 bg-brand-500 flex h-5 items-center gap-[2px] rounded p-1 text-[10px] !font-semibold uppercase !leading-none !text-white sm:h-6 sm:p-[6px]">
                //     <span className="leading-none">Pro</span>
                // </div>
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

const ProLogo = () => {
    return (
        <div className="font-comfortaa flex items-center rounded-[18px] bg-green-200 p-[5px] text-[13px] font-bold leading-none text-white" style={{ background: 'linear-gradient(to right, #FFB843, #FFA004)' }}>
            Pro
        </div>
    );
};
