'use client';

import React, { useState } from 'react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { MenuItem } from '@mui/material';
import cn from 'classnames';
import { Check } from '@app/Components/icons/check';
import Globe from '@app/Components/icons/flags/globe';
import Netherland from '@app/Components/icons/flags/netherland';
import USA from '@app/Components/icons/flags/usa';

export default function LocaleDropdownUiApp() {
    const router = useRouter();
    const pathname = usePathname();
    const [locale, setLocale] = useState('en');

    const dropdownOptions = [
        {
            label: 'en',
            value: 'ENGLISH',
            icon: USA
        },
        {
            label: 'nl',
            value: 'NEDERLANDS',
            icon: Netherland
        }
    ];

    const handleLocale = (label: string) => {
        // Simple implementation for now as requesting "just use en for now"
        // In a real App Router i18n setup, this would change the URL prefix or cookie
        localStorage.setItem('language', label);
        setLocale(label);
        // For now, it doesn't really change the route since we only have 'en' resources anyway
    };

    return (
        <div className="flex items-center">
            <MenuDropdown
                PaperProps={{
                    elevation: 0,
                    sx: {
                        width: 200,
                        overflow: 'hidden',
                        borderRadius: 2,
                        filter: 'drop-shadow(0px 0px 15px rgba(0, 0, 0, 0.15))',
                        mt: 0.5,
                        padding: 0
                    }
                }}
                id="language-menu"
                menuTitle={''}
                menuContent={
                    <>
                        <Globe className="h-6 w-6" />
                        {locale.toUpperCase()}
                    </>
                }
            >
                {dropdownOptions.map((dd: any) => (
                    <MenuItem onClick={() => handleLocale(dd.label)} className="py-4 justify-between hover:bg-black-200" key={dd.value}>
                        <div className={cn('flex gap-3 body3  items-center  ', locale === dd.label && '!text-brand-600 ')}>
                            {React.createElement(dd.icon, { className: 'h-5 w-6' })} {dd?.value}
                        </div>
                        {locale === dd.label && <Check className="h-5 w-5" color="#0C50B4" />}
                    </MenuItem>
                ))}
            </MenuDropdown>
        </div>
    );
}
