import { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import cn from 'classnames';
import { motion } from 'framer-motion';

import { ChevronDown } from '@app/components/icons/chevron-down';
import ActiveLink from '@app/components/ui/links/active-link';
import { useMeasure } from '@app/lib/hooks/use-measure';
import { useAppSelector } from '@app/store/hooks';

type MenuItemProps = {
    name?: string;
    icon: React.ReactNode;
    href: string;
    link: boolean;
    dropdownItems?: DropdownItemProps[];
};

type DropdownItemProps = {
    name: string;
    href: string;
};

export function MenuItem({ name, icon, href, link, dropdownItems }: MenuItemProps) {
    let [isOpen, setIsOpen] = useState(false);
    let [ref, { height }] = useMeasure<HTMLUListElement>();
    let { asPath } = useRouter();

    const workspace = useAppSelector((state) => state.workspace);

    let isChildrenActive = dropdownItems && dropdownItems.some((item) => item.href === asPath);

    useEffect(() => {
        if (isChildrenActive) {
            setIsOpen(true);
        }
    }, []);

    return (
        <div className="mb-2 min-h-[48px] list-none last:mb-0">
            {dropdownItems?.length ? (
                <>
                    <div
                        className={cn('relative flex h-12 cursor-pointer items-center justify-between whitespace-nowrap rounded-lg px-4 text-sm transition-all', isChildrenActive ? 'text-white' : 'text-gray-500 hover:text-brand dark:hover:text-white')}
                        onClick={() => setIsOpen(!isOpen)}
                    >
                        <span className="z-[1] flex items-center ltr:mr-3 rtl:ml-3">
                            <span className="ltr:mr-3 rtl:ml-3">{icon}</span>
                            {name}
                        </span>
                        <span className={`z-[1] transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}>
                            <ChevronDown />
                        </span>

                        {isChildrenActive && <motion.span className="absolute bottom-0 left-0 right-0 h-full w-full rounded-lg bg-brand shadow-large" layoutId="menu-item-active-indicator" />}
                    </div>

                    <div
                        style={{
                            height: isOpen ? height : 0
                        }}
                        className="ease-[cubic-bezier(0.33, 1, 0.68, 1)] overflow-hidden transition-all duration-[350ms]"
                    >
                        <ul ref={ref}>
                            {dropdownItems.map((item, index) => (
                                <li className="first:pt-2" key={index}>
                                    <ActiveLink
                                        href={'/' + workspace.workspaceName + item.href}
                                        className="flex items-center rounded-lg p-3 text-sm text-gray-500 transition-all before:h-1 before:w-1 before:rounded-full before:bg-gray-500 hover:text-brand ltr:pl-6 before:ltr:mr-5 rtl:pr-6 before:rtl:ml-5 dark:hover:text-white"
                                        activeClassName="!text-brand dark:!text-white dark:before:!bg-white before:!bg-brand before:!w-2 before:!h-2 before:-ml-0.5 before:ltr:!mr-[18px] before:rtl:!ml-[18px] !font-medium"
                                    >
                                        {item.name}
                                    </ActiveLink>
                                </li>
                            ))}
                        </ul>
                    </div>
                </>
            ) : (
                <>
                    {link && (
                        <ActiveLink
                            href={'/' + workspace.workspaceName + href}
                            className="relative flex h-12 items-center hover:border-blue-400 hover:bg-blue-50 hover:text-blue-500 whitespace-nowrap rounded-lg px-3 text-sm text-gray-500 transition-all dark:hover:text-white"
                            activeClassName="!text-blue-500"
                        >
                            <span className={`relative z-[1] ${!!name ? 'ltr:mr-3 rtl:ml-3' : 'flex justify-center items-center w-full h-full'}`}>{icon}</span>
                            <span className="relative z-[1]"> {name}</span>

                            {/* {`/${workspace.workspaceName}${href}` === asPath && <motion.span className="absolute bottom-0 left-0 right-0 h-full w-full border-[1px] border-blue-400 rounded-md bg-blue-50" layoutId="menu-item-active-indicator" />} */}
                            {asPath.includes(`/${workspace.workspaceName}${href}`) && <motion.span className="absolute bottom-0 left-0 right-0 h-full w-full border-[1px] border-blue-400 rounded-md bg-blue-50" layoutId="menu-item-active-indicator" />}
                        </ActiveLink>
                    )}
                </>
            )}
        </div>
    );
}
