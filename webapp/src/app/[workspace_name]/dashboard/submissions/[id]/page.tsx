import React from 'react';
import SubmissionDashboardClient from './SubmissionDashboardClient';

export default async function SubmissionDashboardPage({ params }: { params: { workspace_name: string, id: string } }) {
    const { id } = await params;
    
    return (
        <SubmissionDashboardClient submissionId={id} />
    );
}
