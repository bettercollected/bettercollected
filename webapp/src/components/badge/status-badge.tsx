import React from 'react';

import { useTranslation } from 'next-i18next';

import _ from 'lodash';

import { statusProps } from '@app/utils/validationUtils';

export default function StatusBadge({ status, className = '' }: { status: string; className?: string }) {
    const { t } = useTranslation();
    const { currentStatus, cName } = statusProps(status, t);

    return (
        <span className={`text-[9px] flex items-center gap-1 !h-[22px] body4  p-[6px] rounded-[50px] ${cName} ${className}`}>
            <div className="rounded-full !bg-black-800 !h-[6px] !w-[6px]" />
            {_.startCase(currentStatus || '')}
        </span>
    );
}
