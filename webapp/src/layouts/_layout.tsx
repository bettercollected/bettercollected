import React from 'react';

import Logo from '@app/components/ui/logo';
import { useIsMounted } from '@app/lib/hooks/use-is-mounted';
import { useWindowScroll } from '@app/lib/hooks/use-window-scroll';

export function Header(props: any) {
    const windowScroll = useWindowScroll();
    const isMounted = useIsMounted();

    const navClassNames = isMounted && windowScroll.y > 10 ? 'bg-gradient-to-b from-white to-white/80 shadow-card backdrop-blur dark:from-dark dark:to-dark/80' : 'border-b-[0.5px] border-neutral-100 dark:border-neutral-700 bg-white dark:bg-dark';

    return <nav className={`fixed top-0 !z-30 flex w-full items-center justify-between px-5 transition-all duration-300 ltr:right-0 rtl:left-0 h-[68px] ${navClassNames}`}>{props.children}</nav>;
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

            <main className={`relative mb-0 px-5 ${showNavbar ? 'pt-16 sm:pt-[68px]' : ''} sm:pb-20 ${className}`}>{children}</main>
        </div>
    );
}
