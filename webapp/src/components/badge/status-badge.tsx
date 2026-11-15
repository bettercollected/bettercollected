
import { useTranslation } from 'react-i18next';

import _ from 'lodash';

import { StatusPill } from '@app/components/ui/status-pill';
import { statusProps } from '@app/utils/vvalidation-utils';


// statuses statusProps words itself (in the catalogue's language); anything else passes through as its own name
const KNOWN_STATUSES = ['pending', 'success', 'deleted', 'declined', 'expired'];

export default function StatusBadge({ status, className = '' }: { status: string; className?: string }) {
    const { t } = useTranslation();
    const { currentStatus, tone } = statusProps(status, t);

    return (
        <StatusPill tone={tone} className={className}>
            {KNOWN_STATUSES.includes(status.toLowerCase()) ? currentStatus : _.startCase(currentStatus || '')}
        </StatusPill>
    );
}