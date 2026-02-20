'use client';

import SharedSubmissionLayoutClient from '@Components/RespondersPortal/_components/SharedSubmissionLayoutClient';
import React from 'react';

interface SubmissionDashboardLayoutClientProps {
    children: React.ReactNode;
    submissionId: string;
}

export default function SubmissionDashboardLayoutClient({ children, submissionId }: SubmissionDashboardLayoutClientProps) {
    return (
        <SharedSubmissionLayoutClient
            submissionId={submissionId}
            hasCustomDomain={false}
            isUUID={false}
        >
            {children}
        </SharedSubmissionLayoutClient>
    );
}
