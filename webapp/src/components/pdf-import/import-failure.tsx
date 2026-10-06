'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';

import Link from 'next/link';

import { Button } from '@app/shadcn/components/ui/button';
import type { PdfImport } from '@app/store/redux/pdf-import-api';
import { importErrorCode, importErrorNextKey, readWithoutAi } from '@app/utils/pdf-import';

type FailedImport = Pick<PdfImport, 'formId' | 'errorCode' | 'report' | 'aiConsent'>;

/**
 * Why an import stopped and what to do next, in the user's language. The
 * draft form is normally gone (a failed import removes its empty draft); a
 * draft the user had already changed is kept and linked.
 */
export default function ImportFailure({ data, workspaceName }: { data: FailedImport; workspaceName: string }) {
    const { t } = useTranslation('builder');
    const code = importErrorCode(data);
    return (
        <div className="flex flex-col gap-4">
            <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
                <p className="text-sm font-medium">{t(`PDF_IMPORT.ERROR.${code}.MESSAGE`)}</p>
                <p className="mt-1 text-sm">{t(importErrorNextKey(code, readWithoutAi(data)))}</p>
            </div>
            <p className="text-sm text-black-600">{data.formId ? t('PDF_IMPORT.DRAFT_KEPT') : t('PDF_IMPORT.DRAFT_REMOVED')}</p>
            <div className="flex flex-wrap gap-3">
                <Link href={`/${workspaceName}/dashboard/forms/create`}>
                    <Button variant="v2Button">{t('PDF_IMPORT.TRY_ANOTHER_FILE')}</Button>
                </Link>
                {data.formId && (
                    <Link href={`/${workspaceName}/dashboard/forms/${data.formId}/edit`}>
                        <Button>{t('PDF_IMPORT.OPEN_DRAFT')}</Button>
                    </Link>
                )}
            </div>
        </div>
    );
}
