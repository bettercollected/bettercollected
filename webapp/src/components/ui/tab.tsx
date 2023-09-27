import React from 'react';

import { Tab } from '@headlessui/react';
import cn from 'classnames';
import { AnimatePresence, motion } from 'framer-motion';

export { Tab };

//
// Tab Item framer motion variant
//
export function TabItem({ children, className }: React.PropsWithChildren<{ className?: string }>) {
    return (
        <Tab
            className={({ selected }) =>
                cn(
                    'relative p-0',
                    // {
                    //     'border-b-[2px] rounded-[1px]  border-black-900': selected
                    // },
                    'hover:!text-brand-600 focus:outline-none !text-black-800 body6 pb-4  !leading-none',
                    className
                )
            }
        >
            {({ selected }) => (
                <>
                    <span
                        className={cn(
                            `flex w-full justify-between py-2 px-3`,
                            {
                                'bg-black-200 rounded': selected
                            },
                            className
                        )}
                    >
                        {children}
                    </span>
                    {/* {selected && <motion.span className="absolute left-0 right-0 bottom-0 h-[2px] w-full rounded-lg bg-blue-400 dark:bg-gray-400 md:z-0" layoutId="activeTabIndicator" />} */}
                </>
            )}
        </Tab>
    );
}

//
// Tab Panels framer motion variant
//
export function TabPanels({ children, className }: React.PropsWithChildren<{ className?: string }>) {
    return (
        <Tab.Panels className={className}>
            <AnimatePresence mode="wait">
                <>{children}</>
            </AnimatePresence>
        </Tab.Panels>
    );
}

//
// Tab Panel framer motion variant
//
export function TabPanel({ children, className }: React.PropsWithChildren<{ className?: string }>) {
    return (
        <Tab.Panel className={className}>
            <motion.div animate={{ opacity: 1, y: 0 }} initial={{ opacity: 0, y: 32 }} exit={{ opacity: 0, y: -32 }} transition={{ duration: 0.2 }}>
                {children}
            </motion.div>
        </Tab.Panel>
    );
}
