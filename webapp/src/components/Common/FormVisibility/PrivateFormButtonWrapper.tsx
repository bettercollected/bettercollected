import React from 'react';

import Tooltip from '@app/components/Common/DataDisplay/Tooltip';

interface PrivateFormButtonWrapperProps {
    isPrivate?: boolean;
    children: React.ReactElement<any>;
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