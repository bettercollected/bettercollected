'use client';

import FormResponses from '@app/components/form/responses';
import ResponseSegments from '@app/components/form/response-segments';

export default function Page() {
    return (
        <div className="mt-4 px-4 md:px-10 lg:px-28">
            <ResponseSegments />
            <FormResponses />
        </div>
    );
}
