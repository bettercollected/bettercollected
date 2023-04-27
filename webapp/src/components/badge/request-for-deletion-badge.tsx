import React from 'react';

import _ from 'lodash';

import { requestForDeletionProps } from '@app/utils/validationUtils';

export default function RequestForDeletionBadge({ deletionStatus, className = '' }: { deletionStatus: string; className?: string }) {
    const { status, cName } = requestForDeletionProps(deletionStatus);

    return <span className={`text-[9px] font-medium mr-2 px-2.5 py-0.5 rounded ${cName} ${className}`}>{_.startCase(status || '')}</span>;
}
