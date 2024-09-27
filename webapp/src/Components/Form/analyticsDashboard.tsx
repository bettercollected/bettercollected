import FormAnalytics from '@Components/analytics/analytics';

import React from 'react';

export default function FormAnalyticsDashboard() {
    return (
        <div className="mt-[5px] w-full md:max-w-[1200px]">
            <p className="sh1 !text-black-800 !leading-none">Form Analytics</p>
            <FormAnalytics />
        </div>
    );
}
