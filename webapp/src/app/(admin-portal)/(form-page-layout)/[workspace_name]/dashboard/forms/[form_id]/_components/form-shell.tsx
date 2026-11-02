'use client';

import React from 'react';

import { useTranslation } from 'react-i18next';

import { FormBarRestrictedChip } from '@app/components/form/access/restricted-chip';
import { StandardFormDto } from '@app/models/dtos/form';

import { BackToForms, FormBarActions, SkipLink, StatusChip, useFormNav } from './form-nav';
import { FormRail, SectionSwitcher } from './form-side-menu';

/**
 * A form's pages, without the workspace navbar: one sticky bar (back to the
 * forms, the title and its status, the actions), the sections of the form down
 * the side (a sheet from a "current section" row on a phone), and the page.
 * The title is the page's one h1; the bar only truncates it by eye.
 */
export default function FormShell({ form, base, children }: { form: StandardFormDto; base: string; children: React.ReactNode }) {
    const { t } = useTranslation();
    const items = useFormNav(form, base);
    const title = form?.title?.trim() || t('FORM_SHELL.UNTITLED');

    return (
        <div className="min-h-screen w-full bg-white">
            <SkipLink />
            <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-black-400 bg-white px-3 md:px-6">
                <BackToForms />
                <div className="flex min-w-0 flex-col items-start gap-0.5 md:flex-row md:items-center md:gap-2">
                    <h1 className="max-w-full min-w-0 truncate text-base leading-6 font-semibold tracking-title-sm text-black-900" title={title}>
                        {title}
                    </h1>
                    <div className="flex items-center gap-1.5">
                        <StatusChip form={form} />
                        <FormBarRestrictedChip form={form} />
                        {form?.settings?.pinned && <span className="hidden shrink-0 rounded-full bg-black-200 px-2 py-0.5 text-xs font-semibold text-black-700 md:inline-block">{t('FORM.PINNED')}</span>}
                    </div>
                </div>
                <div className="ml-auto shrink-0">
                    <FormBarActions form={form} />
                </div>
            </header>
            <SectionSwitcher items={items} />
            <div className="flex">
                <FormRail items={items} />
                <main id="form-main" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 outline-none md:px-6 lg:px-8">
                    {children}
                </main>
            </div>
        </div>
    );
}
