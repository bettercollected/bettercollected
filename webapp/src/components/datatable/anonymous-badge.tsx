import { Shield as ShieldIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';

/**
 * Anonymity is the product's promise: shown as a state, not as missing data
 * ("- -"). Used for the responder in the responses table and the drawer.
 */
export default function AnonymousBadge() {
    const { t } = useTranslation();
    return (
        <span className="flex w-fit items-center gap-1 rounded-full bg-[#E7F4EE] px-2 py-0.5 text-xs font-medium text-success-700">
            <ShieldIcon className="h-3 w-3" strokeWidth={2} aria-hidden="true" />
            {t('RESPONSES_STAFF.ANONYMOUS')}
        </span>
    );
}
