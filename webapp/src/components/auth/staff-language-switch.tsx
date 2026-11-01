'use client';

import { useId, useRef } from 'react';

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
    const buttons = useRef<Array<HTMLButtonElement | null>>([]);
    if (!staff) return null;

    // The WAI-ARIA radio group model: one tab stop (the checked radio), and the arrow keys
    // (and Home and End) move the choice and focus together.
    const move = (event: React.KeyboardEvent, from: number) => {
        const last = STAFF_LANGUAGES.length - 1;
        const target = { ArrowRight: from === last ? 0 : from + 1, ArrowDown: from === last ? 0 : from + 1, ArrowLeft: from === 0 ? last : from - 1, ArrowUp: from === 0 ? last : from - 1, Home: 0, End: last }[event.key];
        if (target === undefined) return;
        event.preventDefault();
        staff.setLanguage(STAFF_LANGUAGES[target].code);
        buttons.current[target]?.focus();
    };
    return (
        // clicking here keeps the menu open, so the change is seen where it was made
        <li className="list-none px-[20px] py-[10px]" onClick={(event) => event.stopPropagation()}>
            <span id={labelId} className="text-black-600 mb-1 block text-xs">
                {t('STAFF_LANGUAGE.LABEL')}
            </span>
            <div role="radiogroup" aria-labelledby={labelId} className="border-black-400 inline-flex rounded border bg-white p-0.5">
                {STAFF_LANGUAGES.map(({ code, label }, index) => {
                    const selected = staff.language === code;
                    return (
                        <button
                            key={code}
                            ref={(element) => {
                                buttons.current[index] = element;
                            }}
                            type="button"
                            role="radio"
                            aria-checked={selected}
                            lang={code}
                            tabIndex={selected ? 0 : -1}
                            onKeyDown={(event) => move(event, index)}
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
