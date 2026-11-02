'use client';

import AIInsightsCard from '@app/components/form/ai-insights-card';
import FormResponses from '@app/components/form/responses';
import DeliveriesPanel from '@app/components/registration/deliveries-panel';

export default function Page() {
    return (
        <div>
            <div className="mb-4 flex flex-wrap items-center gap-3">
                <AIInsightsCard />
            </div>
            <DeliveriesPanel />
            <FormResponses />
        </div>
    );
}
