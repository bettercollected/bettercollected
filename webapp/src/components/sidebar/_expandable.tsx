import { useRef, useState } from 'react';

import Image from 'next/image';

import cn from 'classnames';
import useClickAway from 'react-use/lib/useClickAway';

import { ChevronDown } from '../icons/chevron-down';
import { ChevronForward } from '../icons/chevron-forward';
import { MenuItem } from '../ui/collapsible-menu';
import Scrollbar from '../ui/scrollbar';
import { menuItems } from './_menu-items';

export default function SidebarExpandable() {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLElement>(null);
    useClickAway(ref, () => {
        setOpen(false);
    });

    const className = 'hidden xl:block relative';

    return (
        <aside
            ref={ref}
            className={cn(
                open ? 'border-0  shadow-expand xs:w-80 xl:w-72 2xl:w-80 ' : 'w-24 border-dashed border-gray-200 ltr:border-r rtl:border-l 2xl:w-28',
                'top-0 z-40 h-full w-full max-w-full  bg-body duration-200 ltr:left-0 rtl:right-0  dark:border-gray-700 dark:bg-dark xl:fixed',
                className
            )}
        >
            <div className={cn('relative flex h-24  items-center  overflow-hidden px-6 py-4 2xl:px-8', open ? 'flex-start' : 'justify-center')}>
                <Image src={'/bettercollected-logo.png'} width="50px" height="50px" priority />
            </div>
            {!open && (
                <div className="absolute hover:shadow-xl hover:text-gray-700 border-solid border-[1px] top-[50%] cursor-pointer right-[-20px] shadow-md p-2 rounded-full">
                    <ChevronForward height="20px" width="20px" />
                </div>
            )}
            <Scrollbar style={{ height: 'calc(100% - 96px)' }}>
                <div className="px-6 pb-5 2xl:px-8">
                    {!open ? (
                        <>
                            <div className="mt-5 2xl:mt-8" onClick={() => setOpen(!open)}>
                                {menuItems.map((item, index) => (
                                    <MenuItem name={'collapse'} key={index} href="" icon={item.icon} />
                                ))}
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="mt-28 cursor-pointer">
                                {menuItems.map((item, index) => (
                                    <MenuItem key={index} name={item.name} href={item.href} icon={item.icon} />
                                ))}
                            </div>
                        </>
                    )}
                </div>
            </Scrollbar>
        </aside>
    );
}
