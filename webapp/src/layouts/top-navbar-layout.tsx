import React from 'react';

import { cn } from '@app/shadcn/util/lib';

import AuthNavbar from '@Components/auth/auth-navbar';

interface LayoutProps {
    isCustomDomain?: boolean;
    isClientDomain?: boolean;
    showHamburgerIcon?: boolean;
    hideMenu?: boolean;
    className?: string;
    childClassName?: string;
    showAuthAccount?: boolean;
    hideSignIn?: boolean;
    showNavbar?: boolean;
    isFooter?: boolean;
}

export default function TopNavLayout({
    children,
    isCustomDomain = false,
    isClientDomain = false,
    hideMenu = false,
    showHamburgerIcon = false,
    className = '',
    childClassName = '',
    showNavbar = false,
    isFooter = false,
    showAuthAccount
}: React.PropsWithChildren<LayoutProps>) {
    return (
        <div className="!bg-black-200 dark:bg-dark z-20 !min-h-screen !min-w-full">
            {showNavbar && <AuthNavbar isFooter={isFooter} isCustomDomain={isCustomDomain} isClientDomain={isClientDomain} showHamburgerIcon={showHamburgerIcon} hideMenu={hideMenu} showPlans={false} showAuthAccount={showAuthAccount} />}
            <main
                className={cn(
                    "bg-black-100 float-none flex w-full px-5 lg:float-right lg:px-10",
                    showNavbar ? "min-h-screen lg:min-h-[calc(100vh-68px)] !mt-[68px]" : "min-h-screen",
                    className
                )}
            >
                <div className={cn("h-full w-full", childClassName)}>{children}</div>
            </main>
        </div>
    );
}
