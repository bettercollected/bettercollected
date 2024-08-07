import React from 'react';

import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';

import AuthAccountMenuDropdown from '@app/Components/auth/account-menu-dropdown';
import ProPlanHoc from '@app/Components/HOCs/pro-plan-hoc';
import Hamburger from '@app/Components/ui/hamburger';
import Logo from '@app/Components/ui/logo';
import { buttonConstant } from '@app/constants/locales/button';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { useIsMounted } from '@app/lib/hooks/use-is-mounted';
import { useWindowScroll } from '@app/lib/hooks/use-window-scroll';

import LocaleDropdownUi from '../ui/locale-dropdown-ui';


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
    handleDrawerToggle: () => {}
};

export function Header(props: any) {
    const windowScroll = useWindowScroll();
    const isMounted = useIsMounted();

    const propClassNames = props?.className ?? '';
    const navClassNames = isMounted && windowScroll.y > 10 ? 'bg-white shadow-card dark:from-dark dark:to-dark/80' : 'border-b-[0.5px] border-neutral-100 dark:border-neutral-700 bg-white dark:bg-dark';

    return <nav className={`!fixed top-0 !z-30 border-b-[1px] border-black-400 flex w-full items-center justify-between px-5 transition-all duration-300 ltr:right-0 rtl:left-0 h-[68px] ${navClassNames} ${propClassNames}`}>{props.children}</nav>;
}

function AuthNavbar({ showHamburgerIcon, showPlans, mobileOpen, handleDrawerToggle, isCustomDomain = false, isFooter = false, isClientDomain = false, hideMenu = false, showAuthAccount }: IAuthNavbarProps) {
    const { t } = useTranslation();
    const inMobile = useIsMobile();
    return (
        <Header className="!z-[1300]">
            <div className="flex flex-row w-full h-full py-2 md:py-0 justify-between items-center">
                <div className="flex gap-4">
                    {inMobile && showHamburgerIcon && <Hamburger isOpen={mobileOpen} className="!shadow-none mr-2 !bg-white hover:!bg-white !text-black-900 !flex !justify-start" onClick={handleDrawerToggle} />}
                    <Logo isCustomDomain={isCustomDomain} isFooter={isFooter} isClientDomain={isClientDomain} />
                </div>
                <div className="flex items-center justify-center gap-7">
                    {!inMobile && (
                        <>
                            <LocaleDropdownUi />
                            {showPlans && (
                                <ProPlanHoc hideChildrenIfPro={true}>
                                    <AppButton>{t(buttonConstant.upgrade)}</AppButton>
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