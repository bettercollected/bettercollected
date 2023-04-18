import React from 'react';

import Link from 'next/link';

import Logo from '@app/components/ui/logo';
import { useIsMounted } from '@app/lib/hooks/use-is-mounted';
import { useWindowScroll } from '@app/lib/hooks/use-window-scroll';

export function Header(props: any) {
    const windowScroll = useWindowScroll();
    const isMounted = useIsMounted();

    return (
        <nav
            className={`fixed top-0 !z-30 flex w-full items-center justify-between px-4 transition-all duration-300 ltr:right-0 rtl:left-0 sm:px-6 lg:px-8 xl:px-10 3xl:px-12 ${
                isMounted && windowScroll.y > 10
                    ? 'h-16 bg-gradient-to-b from-white to-white/80 shadow-card backdrop-blur dark:from-dark dark:to-dark/80 sm:h-24'
                    : 'h-16 border-b-[0.5px] border-neutral-100 dark:border-neutral-700 bg-white dark:bg-dark sm:h-24'
            }`}
        >
            {props.children}
        </nav>
    );
}

interface LayoutProps {
    className?: string;
    hideSignIn?: boolean;
    showNavbar?: boolean;
}

export default function Layout({ children, className = '', showNavbar = false }: React.PropsWithChildren<LayoutProps>) {
    return (
        <div className="!min-h-full !min-w-full bg-brand-100 dark:bg-dark z-20">
            {showNavbar && (
                <Header>
                    <div className="flex justify-between items-center">
                        <Logo />
                    </div>
                </Header>
            )}

            <main className={`relative mb-0 px-4 ${showNavbar ? 'pt-24' : ''} sm:px-6 sm:pt-24 sm:pb-20 lg:px-8 xl:px-10 3xl:px-12 ${className}`}>{children}</main>
        </div>
    );
}
