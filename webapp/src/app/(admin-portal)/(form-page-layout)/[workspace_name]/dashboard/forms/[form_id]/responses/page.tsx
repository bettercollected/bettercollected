'use client';

import AIInsightsCard from '@app/components/form/ai-insights-card';
import FormResponses from '@app/components/form/responses';
import DeliveriesPanel from '@app/components/registration/deliveries-panel';
import ResponseSegments from '@app/components/form/response-segments';

export default function Page() {
    return (
        <div>
            <div className="mb-4 flex flex-wrap items-center gap-3">
                <ResponseSegments />
                <AIInsightsCard />
            </div>
            <DeliveriesPanel />
            <FormResponses />
        </div>
    );
}
