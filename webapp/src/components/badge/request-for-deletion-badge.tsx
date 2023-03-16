import React from 'react';

import _ from 'lodash';

import { requestForDeletionProps } from '@app/utils/validationUtils';

export default function RequestForDeletionBadge({ deletionStatus }: { deletionStatus: string }) {
    const { status, className } = requestForDeletionProps(deletionStatus);

    return <span className={`text-xs font-medium mr-2 px-2.5 py-0.5 rounded ${className}`}>{_.startCase(status || '')}</span>;
}
