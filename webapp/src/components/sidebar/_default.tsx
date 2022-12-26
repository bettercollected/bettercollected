import { useMemo } from 'react';

import Tooltip from '@mui/material/Tooltip/Tooltip';
import cn from 'classnames';

import { authApi, useGetStatusQuery } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

import { useDrawer } from '../drawer-views/context';
import { Close } from '../icons/close';
import { Logout } from '../icons/logout-icon';
import { useModal } from '../modal-views/context';
import Button from '../ui/button';
import { MenuItem } from '../ui/collapsible-menu';
import Logo from '../ui/logo';
import Scrollbar from '../ui/scrollbar';
import { menuItems } from './_menu-items';

export default function Sidebar() {
    const { closeDrawer } = useDrawer();
    const { openModal } = useModal();

    const className = 'xl:block relative';

    useGetStatusQuery('status');

    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select('status'), []);
    const selectGetStatus = useAppSelector(statusQuerySelect);

    const FooterRenderer = ({ icon, name, profileName }: any) => {
        return (
            <div className="flex flex-col justify-center mt-2 border-t-[1.5px] border-gray-100">
                <div
                    onClick={() => openModal('LOGOUT_VIEW')}
                    className={`relative flex flex-row mt-2 py-3 px-4 ${
                        !!name ? 'justify-start' : 'justify-center'
                    } items-center cursor-pointer border-[1.5px] border-red-400 hover:bg-red-50 hover:text-red-500 whitespace-nowrap rounded-lg text-red-500 transition-all dark:hover:text-white`}
                >
                    <div className={!!name ? 'mr-2' : 'mr-0'}>{icon}</div>
                    {!!name && <div>{name}</div>}
                </div>
            </div>
        );
    };

    return (
        <aside className={cn('top-0 z-40 h-full w-full max-w-full border-dashed border-gray-200 bg-body ltr:left-0 ltr:border-r rtl:right-0 rtl:border-l dark:border-gray-700 dark:bg-dark xs:w-80 xl:fixed  xl:w-72 2xl:w-80', className)}>
            <div className="relative flex h-24 items-center justify-between overflow-hidden px-6 py-4 2xl:px-8">
                <div className="flex cursor-pointer items-center p-3 text-2xl font-semibold text-primary">
                    <div className="flex flex-col items-start">
                        <Logo className="!text-base md:!text-base lg:!text-base" />
                        <div className={'text-xs font-normal text-primary opacity-70'}>Collect form responses responsibly.</div>
                    </div>
                </div>
                <div>
                    <Button title="Close" color="white" shape="circle" variant="transparent" size="small" onClick={closeDrawer}>
                        <Close className="h-auto w-2.5" />
                    </Button>
                </div>
            </div>

            <Scrollbar style={{ height: 'calc(100% - 96px)' }}>
                <div className="px-6 h-full pb-5 2xl:px-8">
                    <div className="flex h-full flex-col justify-between">
                        <div className="mt-12">
                            {menuItems.map((item, index) => (
                                <MenuItem key={'default' + item.name + index} name={item.name} href={item.href} icon={item.icon} link={!!item.href} />
                            ))}
                        </div>
                        <FooterRenderer icon={<Logout className={'!w-5 !h-5'} />} name={'Logout'} profileName={selectGetStatus?.data?.payload?.content?.user?.sub} />
                    </div>
                </div>
            </Scrollbar>
        </aside>
    );
}
