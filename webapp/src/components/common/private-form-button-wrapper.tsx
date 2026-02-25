import React from 'react';

import Tooltip from '@app/shadcn/components/ui/tooltip';

interface PrivateFormButtonWrapperProps {
    isPrivate?: boolean;
    children: React.ReactElement<any>;
}

export default function PrivateFormButtonWrapper({ isPrivate, children }: PrivateFormButtonWrapperProps) {
    if (!isPrivate) {
        return children;
    }
    return (
        <Tooltip label="Form is private">
            {children}
        </Tooltip>
    );
}