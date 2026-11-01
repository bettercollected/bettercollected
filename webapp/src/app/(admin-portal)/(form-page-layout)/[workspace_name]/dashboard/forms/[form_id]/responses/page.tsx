'use client';

import AIInsightsCard from '@app/components/form/ai-insights-card';
import FormResponses from '@app/components/form/responses';
import DeliveriesPanel from '@app/components/registration/deliveries-panel';
import ResponseSegments from '@app/components/form/response-segments';

export default function Page() {
    return (
        <div className="mt-4 px-4 md:px-10 lg:px-28">
            <div className="mb-4 flex flex-wrap items-center gap-3">
                <ResponseSegments />
                <AIInsightsCard />
            </div>
            <DeliveriesPanel />
            <FormResponses />
        </div>
    );
}
