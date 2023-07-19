import React from 'react';

import BuilderKeyAndEventListener from './BuilderKeyAndEventListener';
import FormBuilderLeaveListener from './FormBuilderLeaveListener';

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
