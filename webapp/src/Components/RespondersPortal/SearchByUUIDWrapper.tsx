import React from 'react';

import SearchBySubmissionNumber from '@Components/RespondersPortal/SearchBySubmissionNumber';

interface SearchByUUIDWrapperProps {
    children?: React.ReactNode;
}

export default function SearchByUUIDWrapper({ children }: SearchByUUIDWrapperProps) {
    return (
        <div className="md:pl-12  flex gap-6 flex-col xl:flex-row pt-2 pb-20">
            {children}
            <SearchBySubmissionNumber className="hidden lg:block" />
        </div>
    );
}
