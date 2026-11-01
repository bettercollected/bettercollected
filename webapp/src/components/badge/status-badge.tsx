
import { useTranslation } from 'react-i18next';

import _ from 'lodash';

import { statusProps } from '@app/utils/vvalidation-utils';


// statuses statusProps words itself (in the catalogue's language); anything else passes through as its own name
const KNOWN_STATUSES = ['pending', 'success', 'deleted', 'declined', 'expired'];

export default function StatusBadge({ status, className = '' }: { status: string; className?: string }) {
    const { t } = useTranslation();
    const { currentStatus, cName, dotCName } = statusProps(status, t);

    return (
        <span className={`inline-flex h-[22px] w-fit items-center gap-1.5 rounded-full px-2.5 text-xs font-medium ${cName} ${className}`}>
            <div className={`h-1.5 w-1.5 rounded-full ${dotCName}`} />
            {KNOWN_STATUSES.includes(status.toLowerCase()) ? currentStatus : _.startCase(currentStatus || '')}
        </span>
    );
}