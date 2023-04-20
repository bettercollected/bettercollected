import React from 'react';

import { ChevronLeft } from '@mui/icons-material';

import AuthNavbar from '@app/components/auth/navbar';
import BackButton from '@app/components/settings/back';
import { SettingsSidebar } from '@app/components/settings/sidebar';
import Hamburger from '@app/components/ui/hamburger';

export default function ManageWorkspaceLayout({ children }: any) {
    return (
        <div className="mt-[68px] flex items-center flex-col">
            <AuthNavbar showHamburgerIcon={false} />
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
