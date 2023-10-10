import React from 'react';

import BuilderKeyAndEventListener from '@Components/Listeners/BuilderKeyAndEventListener';
import FormBuilderLeaveListener from '@Components/Listeners/FormBuilderLeaveListener';

interface IFormBuilderContainerWrapperProps {
    children: React.ReactNode | React.ReactNode[];
}

export default function FormBuilderContainerWrapper({ children }: IFormBuilderContainerWrapperProps) {
    return (
        <FormBuilderLeaveListener>
            <BuilderKeyAndEventListener>{children}</BuilderKeyAndEventListener>
        </FormBuilderLeaveListener>
    );
}