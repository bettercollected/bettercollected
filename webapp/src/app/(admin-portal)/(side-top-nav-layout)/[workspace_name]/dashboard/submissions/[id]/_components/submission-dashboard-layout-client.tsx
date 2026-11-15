'use client';

import SharedSubmissionLayoutClient from '@Components/responder-portal/shared-submission-layout-client';
import React from 'react';

interface SubmissionDashboardLayoutClientProps {
    children: React.ReactNode;
    submissionId: string;
}

export default function SubmissionDashboardLayoutClient({ children, submissionId }: SubmissionDashboardLayoutClientProps) {
    // The respondent's view of a submission, drawn inside the creator app: its page ground and its header band are the
    // respondent page's own (a light grey and white), which do not match the app's canvas around them. Here the ground
    // is the canvas and the header a hairline on it; the response card is left as it is.
    return (
        <div className="[&>div]:bg-canvas! [&_header]:border-b-hairline-strong! [&_header]:bg-transparent!">
            <SharedSubmissionLayoutClient
                submissionId={submissionId}
                hasCustomDomain={false}
                isUUID={false}
            >
                {children}
            </SharedSubmissionLayoutClient>
        </div>
    );
}
