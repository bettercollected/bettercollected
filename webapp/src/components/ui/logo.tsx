import AnchorLink from '@app/components/ui/links/anchor-link';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import BetterCollectedLogo from '@app/views/atoms/Icons/BetterCollectedLogo';

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
            <BetterCollectedLogo className="h-full w-full" />
            {isProAndIsWorkspaceAdmin && showProTag && <ProLogo />}
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

export const ProLogo = () => {
    return (
        <div className="font-comfortaa flex h-fit flex-row  items-center rounded-[18px] bg-green-200 px-[5px] pb-[3px] pt-[5px] text-[13px] font-bold leading-[13px] text-white" style={{ background: 'linear-gradient(to right, #FFB843, #FFA004)' }}>
            <span>Pro</span>
        </div>
    );
};
