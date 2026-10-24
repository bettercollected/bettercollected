'use client';

import { useTranslation } from 'react-i18next';

import { googleFormsImport } from '@app/constants/locales/google-forms-import';
import { cn } from '@app/shadcn/util/lib';

interface GoogleFormsImportNoticeProps {
    mode: 'readonly' | 'off';
    className?: string;
}

/** Why Google Forms imports are not offered: read-only or turned off on this instance. */
export default function GoogleFormsImportNotice({ mode, className }: GoogleFormsImportNoticeProps) {
    const { t } = useTranslation();
    const strings = mode === 'readonly' ? googleFormsImport.readonly : googleFormsImport.off;
    return (
        <div role="note" className={cn('rounded-lg border border-black-300 bg-black-100 px-4 py-3 text-sm', className)}>
            <p className="font-medium text-black-900">{t(strings.title)}</p>
            <p className="mt-1 text-black-700">{t(strings.description)}</p>
        </div>
    );
}
