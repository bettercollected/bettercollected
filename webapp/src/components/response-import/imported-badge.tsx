import { FileUp as ImportIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';

/** Marks a response that came from a CSV import (docs/response-import.md), next to the anonymous mark. */
export default function ImportedBadge() {
    const { t } = useTranslation();
    return (
        <span title={t('RESPONSE_IMPORT.IMPORTED_TITLE')} className="flex w-fit items-center gap-1 rounded-full bg-black-100 px-2 py-0.5 text-xs font-medium text-black-700">
            <ImportIcon className="h-3 w-3" strokeWidth={2} aria-hidden="true" />
            {t('RESPONSE_IMPORT.IMPORTED_BADGE')}
        </span>
    );
}
