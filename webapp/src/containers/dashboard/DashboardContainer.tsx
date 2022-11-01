import React from 'react';

import { useIsDarkMode } from '@app/lib/hooks/use-is-dark-mode';

interface IDashboardContainer {
    companyJson: any;
}

export default function DashboardContainer({ companyJson }: IDashboardContainer) {
    const { isDarkMode } = useIsDarkMode();
    console.log(companyJson);

    return <h1>Dashboard</h1>;
}
