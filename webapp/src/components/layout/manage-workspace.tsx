import React from 'react';

import AuthNavbar from '@app/components/auth/navbar';
import BackButton from '@app/components/settings/back';
import { SettingsSidebar } from '@app/components/settings/sidebar';
import Hamburger from '@app/components/ui/hamburger';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';

export default function ManageWorkspaceLayout({ children }: any) {
    const breakpoint = useBreakpoint();
    return (
        <div className="mt-[68px] flex items-center flex-col">
            <AuthNavbar showHamburgerIcon={false} showPlans={['sm'].indexOf(breakpoint) !== -1} />
            <div className="grid grid-cols-2 lg:grid-cols-3 lg:space-x-6 !w-full">
                <div className="hidden lg:block pl-5 md:pl-10 lg:pl-28 col-span-1">
                    <SettingsSidebar />
                </div>
                <div className="lg:hidden pt-10 lg:pt-0 flex justify-between col-span-2 px-5 md:px-10">
                    <BackButton />
                    <Hamburger isOpen={false} className="!shadow-none !bg-transparent !text-black-900 !flex !justify-start" onClick={() => {}} />
                </div>
                <div className="col-span-2 lg:screen-navbar lg:pt-10 px-5 md:px-10 lg:pr-28 lg:pl-0">{children}</div>
            </div>
        </div>
    );
}
