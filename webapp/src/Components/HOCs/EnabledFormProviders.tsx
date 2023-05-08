import React from 'react';

import { useGetEnabledProvidersQuery } from '@app/store/providers/api';

interface IEnabledFormProvidersProps {
    children: React.ReactNode | React.ReactNode[];
}

export default function EnabledFormProviders({ children }: IEnabledFormProvidersProps) {
    useGetEnabledProvidersQuery(undefined, {
        pollingInterval: 30000
    });

    return <>{children}</>;
}
