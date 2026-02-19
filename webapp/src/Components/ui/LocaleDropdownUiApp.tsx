'use client';

import { Check } from '@app/Components/icons/check';
import Globe from '@app/Components/icons/flags/globe';
import Netherland from '@app/Components/icons/flags/netherland';
import USA from '@app/Components/icons/flags/usa';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import cn from 'classnames';
import { usePathname, useRouter } from 'next/navigation';
import React, { useState } from 'react';

export default function LocaleDropdownUiApp() {
    const [locale, setLocale] = useState('en');
    const [open, setOpen] = useState(false);

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
        setOpen(false);
        // For now, it doesn't really change the route since we only have 'en' resources anyway
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <div className="flex items-center gap-2 cursor-pointer text-sm font-medium">
                    <Globe className="h-6 w-6" />
                    {locale.toUpperCase()}
                </div>
            </PopoverTrigger>
            <PopoverContent className="w-[200px] p-0 rounded-lg drop-shadow-xl mt-2" align="end">
                <div className="flex flex-col">
                    {dropdownOptions.map((dd: any) => (
                        <div
                            key={dd.value}
                            onClick={() => handleLocale(dd.label)}
                            className="flex items-center justify-between px-4 py-3 hover:bg-black-100 cursor-pointer text-sm"
                        >
                            <div className={cn('flex gap-3 body3 items-center', locale === dd.label && '!text-brand-600')}>
                                {React.createElement(dd.icon, { className: 'h-5 w-6' })} {dd?.value}
                            </div>
                            {locale === dd.label && <Check className="h-5 w-5" color="#0C50B4" />}
                        </div>
                    ))}
                </div>
            </PopoverContent>
        </Popover>
    );
}
