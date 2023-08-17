import React, { useMemo } from 'react';

import FormProviderContext from '@app/Contexts/FormProviderContext';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { useGetEnabledProvidersQuery } from '@app/store/providers/api';

interface IEnabledFormProvidersProps {
    children: React.ReactNode | React.ReactNode[];
}

export default function EnabledFormProviders({ children }: IEnabledFormProvidersProps) {
    const { data, isLoading, isError } = useGetEnabledProvidersQuery(undefined, {
        pollingInterval: 120000
    });

    const formProviders = useMemo(() => (isError ? [] : data ?? []), [isError, data]);

    if (isLoading) return <FullScreenLoader />;

    return <FormProviderContext.Provider value={formProviders}>{children}</FormProviderContext.Provider>;
}
