/* eslint-disable react/no-array-index-key */
import React from 'react';

import ActiveLink from '@app/components/ui/links/active-link';

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
