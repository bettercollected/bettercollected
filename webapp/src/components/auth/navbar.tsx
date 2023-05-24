import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { MenuItem } from '@mui/material';
import cn from 'classnames';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import { DRAWER_VIEW } from '@app/components/drawer-views/context';
import ProPlanHoc from '@app/components/hoc/pro-plan-hoc';
import Button from '@app/components/ui/button';
import Hamburger from '@app/components/ui/hamburger';
import Logo from '@app/components/ui/logo';
import { buttonConstant } from '@app/constants/locales/buttons';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useIsMounted } from '@app/lib/hooks/use-is-mounted';
import { useWindowScroll } from '@app/lib/hooks/use-window-scroll';

import { Check } from '../icons/check';
import Globe from '../icons/flags/globe';
import Nepal from '../icons/flags/nepal';
import Netherland from '../icons/flags/netherland';
import USA from '../icons/flags/usa';

interface IAuthNavbarProps {
    hideMenu?: boolean;
    isCustomDomain?: boolean;
    isClientDomain?: boolean;
    showHamburgerIcon?: boolean;
    showPlans?: boolean;
    mobileOpen?: boolean;
    showAuthAccount?: boolean;
    handleDrawerToggle?: () => void;
    drawerView?: DRAWER_VIEW;
}

AuthNavbar.defaultProps = {
    hideMenu: false,
    showPlans: true,
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
    const navClassNames = isMounted && windowScroll.y > 10 ? 'bg-gradient-to-b from-white to-white/80 shadow-card backdrop-blur dark:from-dark dark:to-dark/80' : 'border-b-[0.5px] border-neutral-100 dark:border-neutral-700 bg-white dark:bg-dark';

    return <nav className={`fixed top-0 !z-30 flex w-full items-center justify-between px-5 lg:pr-10 transition-all duration-300 ltr:right-0 rtl:left-0 h-[68px] ${navClassNames} ${propClassNames}`}>{props.children}</nav>;
}

export default function AuthNavbar({ showHamburgerIcon, showPlans, mobileOpen, handleDrawerToggle, isCustomDomain = false, isClientDomain = false, hideMenu = false, drawerView = 'DASHBOARD_SIDEBAR', showAuthAccount }: IAuthNavbarProps) {
    const screenSize = useBreakpoint();
    const { t } = useTranslation();
    const router = useRouter();
    const { pathname, asPath, query } = router;
    const [language, setLanguage] = useState(router.locale ?? 'EN');
    const isMobileView = () => {
        switch (screenSize) {
            case 'xs':
            case '2xs':
            case 'sm':
            case 'md':
                return true;
            default:
                return false;
        }
    };

    const dropdownOptions = [
        {
            label: 'en',
            value: 'ENGLISH',
            icon: USA
        },
        {
            label: 'nl',
            value: 'DUTCH',
            icon: Netherland
        },
        {
            label: 'np',
            value: 'NEPALI',
            icon: Nepal
        }
    ];

    const handleLanguage = (language: string) => {
        router.push({ pathname, query }, asPath, { locale: language.toLowerCase() });
        localStorage.setItem('language', language);
        setLanguage(language);
    };

    return (
        <Header className="!z-[1300]">
            <div className="flex flex-row w-full h-full py-2 md:py-0 justify-between items-center">
                <div className="flex gap-4">
                    {isMobileView() && showHamburgerIcon && <Hamburger isOpen={mobileOpen} className="!shadow-none mr-2 !bg-white hover:!bg-white !text-black-900 !flex !justify-start" onClick={handleDrawerToggle} />}
                    <Logo isCustomDomain={isCustomDomain} isClientDomain={isClientDomain} />
                </div>
                <div className="flex items-center justify-center gap-7">
                    {!isMobileView() && (
                        <>
                            <div className="flex items-center">
                                <MenuDropdown
                                    PaperProps={{
                                        elevation: 0,
                                        sx: {
                                            width: 200,
                                            overflow: 'hidden',
                                            borderRadius: 2,
                                            filter: 'drop-shadow(0px 0px 15px rgba(0, 0, 0, 0.15))',
                                            mt: 0.5,
                                            padding: 0
                                        }
                                    }}
                                    id="language-menu"
                                    menuTitle={''}
                                    menuContent={
                                        <>
                                            <Globe className="h-6 w-6" />
                                            {language.toUpperCase()}
                                        </>
                                    }
                                >
                                    {dropdownOptions.map((dd: any) => (
                                        <MenuItem onClick={() => handleLanguage(dd.label)} className="py-4 justify-between hover:bg-black-200" key={dd.value}>
                                            <div className={cn('flex gap-3 body3  items-center  ', language === dd.label && '!text-brand-600 ')}>
                                                {React.createElement(dd.icon, { className: 'h-5 w-6' })} {dd?.value}
                                            </div>
                                            {language === dd.label && <Check className="h-5 w-5" color="#0C50B4" />}
                                        </MenuItem>
                                    ))}
                                </MenuDropdown>
                            </div>
                            {showPlans && (
                                <ProPlanHoc hideChildrenIfPro={true}>
                                    <Button size="small">{t(buttonConstant.upgrade)}</Button>
                                </ProPlanHoc>
                            )}
                        </>
                    )}
                    {showAuthAccount && <AuthAccountMenuDropdown hideMenu={hideMenu} />}
                </div>
            </div>
        </Header>
    );
}
