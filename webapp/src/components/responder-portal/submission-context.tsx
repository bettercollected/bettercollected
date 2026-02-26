'use client';

import React, { createContext, useContext } from 'react';

interface SubmissionContextType {
    data: any;
    isLoading: boolean;
    isError: boolean;
    handleRequestForDeletion: () => void;
    hasCustomDomain: boolean;
    workspaceName?: string;
}

const SubmissionContext = createContext<SubmissionContextType | undefined>(undefined);

export function SubmissionProvider({
    children,
    value
}: {
    children: React.ReactNode;
    value: SubmissionContextType;
}) {
    return (
        <SubmissionContext.Provider value={value}>
            {children}
        </SubmissionContext.Provider>
    );
}

export function useSubmissionContext() {
    const context = useContext(SubmissionContext);
    if (!context) {
        throw new Error('useSubmissionContext must be used within a SubmissionProvider');
    }
    return context;
}
