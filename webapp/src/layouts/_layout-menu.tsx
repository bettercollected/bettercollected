import React from 'react';

// import ConnectWallet from '@app/components/connect-wallet/wallet-button';
import { useDrawer } from '@app/components/drawer-views/context';
import { Close } from '@app/components/icons/close';
// import SearchButton from '@app/components/search-view/search-button';
// import SettingsButton from '@app/components/settings/settings-button';
import Button from '@app/components/ui/button';
import ActiveLink from '@app/components/ui/links/active-link';
import Logo from '@app/components/ui/logo';
import Scrollbar from '@app/components/ui/scrollbar';

const MenuLinks: Array<any> = [];

export function MenuItems() {
    return (
        <div className="flex items-center xl:px-10 2xl:px-14 3xl:px-16">
            {MenuLinks.length !== 0 &&
                MenuLinks.map((item, index) => (
                    <ActiveLink key={index} href={item.href} className="mx-4 text-sm font-medium uppercase text-gray-600 transition first:ml-0 last:mr-0 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white" activeClassName="text-gray-900">
                        {item.name}
                    </ActiveLink>
                ))}
        </div>
    );
}

export default function DrawerMenu() {
    const { closeDrawer } = useDrawer();
    return (
        <div className="relative w-full max-w-full bg-white dark:bg-dark xs:w-80">
            <div className="flex h-24 items-center justify-between overflow-hidden p-1">
                <Logo />
                <div className="md:hidden">
                    <Button title="Close" color="white" shape="circle" variant="transparent" size="small" onClick={closeDrawer}>
                        <Close className="h-auto w-2.5" />
                    </Button>
                </div>
            </div>

            <Scrollbar style={{ height: 'calc(100% - 96px)' }}>
                <div className="flex flex-col pt-6 px-6 pb-16 sm:pb-20 gap-2">
                    <h1>Hello sidebar</h1>
                </div>
            </Scrollbar>
        </div>
    );
}
