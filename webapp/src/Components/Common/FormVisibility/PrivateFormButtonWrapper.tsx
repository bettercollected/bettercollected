import React from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';

interface PrivateFormButtonWrapperProps {
    isPrivate?: boolean;
    children: React.ReactElement;
}

export default function PrivateFormButtonWrapper({ isPrivate, children }: PrivateFormButtonWrapperProps) {
    if (!isPrivate) {
        return children;
    }
    return (
        <Tooltip leaveDelay={300} title="Form is private">
            {children}
        </Tooltip>
    );
}