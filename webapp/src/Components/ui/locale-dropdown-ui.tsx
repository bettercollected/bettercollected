import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { MenuItem } from '@mui/material';
import cn from 'classnames';

import { Check } from '@app/Components/icons/check';
import Globe from '@app/Components/icons/flags/globe';
import Netherland from '@app/Components/icons/flags/netherland';
import USA from '@app/Components/icons/flags/usa';

export default function LocaleDropdownUi() {

    // Initialize from localStorage, fallback to 'en'
    const [locale, setLocale] = useState(() => {
        const saved = localStorage.getItem('language');
        return saved ? saved.toUpperCase() : 'EN';
    });

    // Optional: sync when component mounts (in case of tab sync or hydration)
    useEffect(() => {
        const saved = localStorage.getItem('language');
        if (saved && saved.toUpperCase() !== locale) {
            setLocale(saved.toUpperCase());
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const dropdownOptions = [
        {
            label: 'en',
            value: 'ENGLISH',
            icon: USA,
        },
        {
            label: 'nl',
            value: 'NEDERLANDS',
            icon: Netherland,
        },
    ];

    const handleLocale = (label: string) => {
        const newLocale = label.toLowerCase();
        // Save to localStorage
        localStorage.setItem('language', newLocale);

        // Update UI state
        setLocale(label.toUpperCase());
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
                        padding: 0,
                    },
                }}
                id="language-menu"
                menuTitle={''}
                menuContent={
                    <>
                        <Globe className="h-6 w-6" />
                        {locale}
                    </>
                }
            >
                {dropdownOptions.map((dd) => (
                    <MenuItem
                        onClick={() => handleLocale(dd.label)}
                        className="py-4 justify-between hover:bg-black-200"
                        key={dd.value}
                    >
                        <div
                            className={cn(
                                'flex gap-3 body3 items-center',
                                locale.toLowerCase() === dd.label && '!text-brand-600'
                            )}
                        >
                            {React.createElement(dd.icon, { className: 'h-5 w-6' })} {dd.value}
                        </div>
                        {locale.toLowerCase() === dd.label && (
                            <Check className="h-5 w-5" color="#0C50B4" />
                        )}
                    </MenuItem>
                ))}
            </MenuDropdown>
        </div>
    );
}