'use client';

import React from 'react';
import { Menu } from 'lucide-react';

import AuthAccountMenuDropdown from '@app/Components/auth/account-menu-dropdown';
import LogoApp from '@app/Components/ui/LogoApp';
import { Button } from '@app/shadcn/components/ui/button';

export default function AuthNavbarApp({ handleDrawerToggle }: any) {
    return (
        <header className="fixed left-0 right-0 top-0 z-[1201] w-full border-b border-gray-200 bg-white shadow-none h-[68px] flex items-center justify-between px-5 lg:px-10">
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="icon"
                    className="p-1 lg:hidden"
                    onClick={handleDrawerToggle}
                >
                    <Menu className="h-6 w-6" />
                    <span className="sr-only">Open menu</span>
                </Button>
                <LogoApp isCustomDomain={false} isFooter={false} isClientDomain={false} />
            </div>
            <div className="flex items-center gap-4">
                <AuthAccountMenuDropdown hideMenu={false} isClientDomain={false} />
            </div>
        </header>
    );
}
