import React, { useState } from 'react';

import { useRouter } from 'next/router';

import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { MenuItem } from '@mui/material';
import cn from 'classnames';

import { Check } from '@app/components/icons/check';
import Globe from '@app/components/icons/flags/globe';
import Netherland from '@app/components/icons/flags/netherland';
import USA from '@app/components/icons/flags/usa';


export default function LocaleDropdownUi() {
    const router = useRouter();
    const { pathname, asPath, query } = router;
    const [locale, setLocale] = useState(router.locale ?? 'EN');
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
        router.push({ pathname, query }, asPath, { locale: label.toLowerCase() });
        localStorage.setItem('language', label);
        setLocale(label);
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