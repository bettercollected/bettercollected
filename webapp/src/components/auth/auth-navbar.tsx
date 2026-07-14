import React from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import Hamburger from '@app/components/ui/hamburger';
import Logo from '@app/components/ui/logo';
import Link from 'next/link';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { buttonConstant } from '@app/constants/locales/button';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { useIsMounted } from '@app/lib/hooks/use-is-mounted';
import { useWindowScroll } from '@app/lib/hooks/use-window-scroll';
import ProPlanHoc from '@Components/hocs/pro-plan-hoc';


interface IAuthNavbarProps {
    hideMenu?: boolean;
    isFooter?: boolean;
    isCustomDomain?: boolean;
    isClientDomain?: boolean;
    showHamburgerIcon?: boolean;
    showPlans?: boolean;
    mobileOpen?: boolean;
    showAuthAccount?: boolean;
    handleDrawerToggle?: () => void;
    workspaceIdentity?: boolean;
    /** Constrain the navbar CONTENT to the same container as the page body
     *  (pass the body's padding classes) so their left edges align. */
    containerClassName?: string;
}

AuthNavbar.defaultProps = {
    hideMenu: false,
    showPlans: true,
    isFooter: false,
    isCustomDomain: false,
    isClientDomain: false,
    showHamburgerIcon: true,
    isMobileView: false,
    showAuthAccount: true,
    handleDrawerToggle: () => { }
};

export function Header(props: any) {
    const windowScroll = useWindowScroll();
    const isMounted = useIsMounted();

    const propClassNames = props?.className ?? '';
    const navClassNames = isMounted && windowScroll.y > 10 ? 'bg-white shadow-card dark:from-dark dark:to-dark/80' : 'border-b-[0.5px] border-neutral-100 dark:border-neutral-700 bg-white dark:bg-dark';

    return <nav className={`!fixed top-0 !z-30 border-b-[1px] border-black-400 flex w-full items-center justify-between px-5 transition-all duration-300 ltr:right-0 rtl:left-0 h-[68px] ${navClassNames} ${propClassNames}`}>{props.children}</nav>;
}

function WorkspaceIdentity() {
    const workspace = useAppSelector(selectWorkspace);
    if (!workspace?.workspaceName) return null;
    const title = workspace?.title || workspace?.workspaceName;
    return (
        <Link href={`/${workspace.workspaceName}/dashboard`} className="flex min-w-0 items-center gap-2.5 outline-none">
            {workspace?.profileImage ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={workspace.profileImage} alt="" className="h-7 w-7 shrink-0 rounded-md object-cover" />
            ) : (
                <span className="bg-brand-100 text-brand-600 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-xs font-bold">{(title?.[0] || 'W').toUpperCase()}</span>
            )}
            <span className="text-black-900 truncate text-sm font-semibold">{title}</span>
        </Link>
    );
}

function AuthNavbar({ showHamburgerIcon, showPlans, mobileOpen, handleDrawerToggle, isCustomDomain = false, isFooter = false, isClientDomain = false, hideMenu = false, showAuthAccount, workspaceIdentity = false, containerClassName }: IAuthNavbarProps) {
    const { t } = useTranslation();
    const inMobile = useIsMobile();
    return (
        <Header className={`!z-[1300] ${containerClassName ? '!px-0' : ''}`}>
            <div className={`flex flex-row w-full h-full py-2 md:py-0 justify-between items-center ${containerClassName ?? ''}`}>
                <div className="flex gap-4">
                    {inMobile && showHamburgerIcon && <Hamburger isOpen={mobileOpen} className="!shadow-none mr-2 !bg-white hover:!bg-white !text-black-900 !flex !justify-start" onClick={handleDrawerToggle} />}
                    {/* Admin surfaces lead with the WORKSPACE identity, not the
                        product logo (de-brand decision — bettercollected appears only
                        as a subtle "Powered by"). The login page keeps the brand, so
                        this is opt-in per surface. */}
                    {workspaceIdentity ? <WorkspaceIdentity /> : <Logo isCustomDomain={isCustomDomain} isFooter={isFooter} isClientDomain={isClientDomain} />}
                </div>
                <div className="flex items-center justify-center gap-7">
                    {!inMobile && (
                        <>
                            {/* <LocaleDropdownUiApp /> */}
                            {showPlans && (
                                <ProPlanHoc hideChildrenIfPro={true}>
                                    <Button>{t(buttonConstant.upgrade)}</Button>
                                </ProPlanHoc>
                            )}
                        </>
                    )}
                    {showAuthAccount && <AuthAccountMenuDropdown hideMenu={hideMenu} isClientDomain={isClientDomain} />}
                </div>
            </div>
        </Header>
    );
}

export default React.memo(AuthNavbar);