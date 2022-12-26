import { useMemo, useRef, useState } from 'react';

import Tooltip from '@mui/material/Tooltip/Tooltip';
import cn from 'classnames';
import useClickAway from 'react-use/lib/useClickAway';

import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { authApi, useGetStatusQuery } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

import { ChevronForward } from '../icons/chevron-forward';
import { Logout } from '../icons/logout-icon';
import { useModal } from '../modal-views/context';
import { MenuItem } from '../ui/collapsible-menu';
import Hamburger from '../ui/hamburger';
import Scrollbar from '../ui/scrollbar';
import { menuItems } from './_menu-items';

export default function SidebarExpandable() {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLElement>(null);

    const { openModal } = useModal();

    useGetStatusQuery('status');

    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select('status'), []);
    const selectGetStatus = useAppSelector(statusQuerySelect);

    useClickAway(ref, () => {
        setOpen(false);
    });

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
    // !bg-[#3b82f6]

    const className = 'top-24 hidden border-r-[1px] sm:block relative h-[calc(100%-4rem)] sm:h-[calc(100%-6rem)]';

    return (
        <aside
            ref={ref}
            className={cn(
                open ? 'border-0 shadow-expand xs:w-80 xl:w-72 2xl:w-80 ' : 'w-24 border-dashed border-gray-200 ltr:border-r rtl:border-l 2xl:w-28',
                'top-0 z-40 h-full w-full max-w-full  bg-body duration-200 ltr:left-0 rtl:right-0  dark:border-gray-700 dark:bg-dark xl:fixed',
                className
            )}
        >
            <div className={cn('relative flex h-24 items-center overflow-hidden px-9 py-4 2xl:px-11', open ? 'flex-start' : 'justify-center')}>
                {!open && <Hamburger isOpen={open} className="!w-10 !h-10 !bg-white !text-black" onClick={() => setOpen(!open)} />}
                {open && (
                    <div className="flex items-center justify-center h-10 cursor-pointer overflow-hidden" onClick={() => setOpen(false)}>
                        <ChevronForward className={`rotate-180 w-3 h-3 text-gray-800 mr-2`} />
                        <p className="m-0 p-0">Collapse</p>
                    </div>
                )}
            </div>

            <Scrollbar style={{ height: 'calc(100% - 96px)' }}>
                <div className="h-full px-6 pb-5 2xl:px-8">
                    {!open ? (
                        <div className="flex h-full flex-col justify-between">
                            <div className="mt-8 mb-2">
                                {menuItems.map((item, index) => (
                                    <MenuItem key={index} link={!!item.href} href={item.href} icon={item.icon} />
                                ))}
                            </div>
                            <FooterRenderer icon={<Logout className={'!w-5 !h-5'} />} profileName={selectGetStatus?.data?.payload?.content?.user?.sub} />
                        </div>
                    ) : (
                        <div className="flex h-full flex-col justify-between">
                            <div className="mt-6 mb-2 cursor-pointer">
                                {menuItems.map((item, index) => (
                                    <MenuItem key={index} link={!!item.href} name={item.name} href={item.href} icon={item.icon} />
                                ))}
                            </div>
                            <FooterRenderer icon={<Logout className={'!w-5 !h-5'} />} name={'Logout'} profileName={selectGetStatus?.data?.payload?.content?.user?.sub} />
                        </div>
                    )}
                </div>
            </Scrollbar>
        </aside>
    );
}
