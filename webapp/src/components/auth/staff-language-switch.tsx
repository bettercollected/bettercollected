'use client';

import { useId } from 'react';

import { useTranslation } from 'react-i18next';

import { useStaffLanguage } from '@app/components/staff-language-provider';
import { STAFF_LANGUAGES } from '@app/lib/staff-language';
import { cn } from '@app/shadcn/util/lib';

/**
 * "English / Nederlands" in the account menu: a radio group of two. Offered only
 * inside the dashboard (where a StaffLanguageProvider is), and each name is
 * written in its own language (and marked with `lang`) so it can be found
 * whatever the current language is.
 */
export default function StaffLanguageSwitch() {
    const { t } = useTranslation();
    const staff = useStaffLanguage();
    const labelId = useId();
    if (!staff) return null;
    return (
        // clicking here keeps the menu open, so the change is seen where it was made
        <li className="list-none px-[20px] py-[10px]" onClick={(event) => event.stopPropagation()}>
            <span id={labelId} className="text-black-600 mb-1 block text-xs">
                {t('STAFF_LANGUAGE.LABEL')}
            </span>
            <div role="radiogroup" aria-labelledby={labelId} className="border-black-400 inline-flex rounded border bg-white p-0.5">
                {STAFF_LANGUAGES.map(({ code, label }) => {
                    const selected = staff.language === code;
                    return (
                        <button
                            key={code}
                            type="button"
                            role="radio"
                            aria-checked={selected}
                            lang={code}
                            onClick={() => staff.setLanguage(code)}
                            className={cn('rounded-md px-3 py-1 text-sm', selected ? 'bg-brand-100 text-black-900 font-semibold' : 'text-black-700 hover:bg-black-200 font-medium')}
                        >
                            {label}
                        </button>
                    );
                })}
            </div>
        </li>
    );
}
