import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import BetterCollectedLogo from '@Components/icons/bettercollected-logo';
import Link from 'next/link';

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
            <BetterCollectedLogo className="h-[19px]" />
            {isProAndIsWorkspaceAdmin && showProTag && <ProLogo />}
        </div>
    );

    return isLink ? (
        <Link href={url} target={isCustomDomain && isFooter ? '_blank' : undefined} className="w-fit outline-none" {...props}>
            {logo}
        </Link>
    ) : (
        logo
    );
};

Logo.defaultProps = {
    className: '',
    showProTag: true
};
export default Logo;

// A quiet plan chip on the trust ramp. The old orange-gradient pill put white
// text on #FFA004 (~2.1:1 contrast) in a display face used nowhere else.
export const ProLogo = () => {
    return (
        <div className="flex h-fit flex-row items-center rounded-full bg-[#FBF3E4] px-2 py-[2px] text-[11px] font-semibold leading-[14px] text-[#B26B00]">
            <span>Pro</span>
        </div>
    );
};
