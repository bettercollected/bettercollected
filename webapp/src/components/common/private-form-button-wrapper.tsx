import React from 'react';

import { useTranslation } from 'react-i18next';

import Tooltip from '@app/shadcn/components/ui/tooltip';

interface PrivateFormButtonWrapperProps {
    isPrivate?: boolean;
    children: React.ReactElement<any>;
}

export default function PrivateFormButtonWrapper({ isPrivate, children }: PrivateFormButtonWrapperProps) {
    const { t } = useTranslation();
    if (!isPrivate) {
        return children;
    }
    return (
        <Tooltip label={t('STAFF.FORM.PRIVATE_TOOLTIP')}>
            {children}
        </Tooltip>
    );
}