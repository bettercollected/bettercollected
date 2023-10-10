import React, { ReactNode } from 'react';

import AppButton, { AppButtonProps } from '@Components/Common/Input/Button/AppButton';

interface ModalbuttonProps extends AppButtonProps {
    children: ReactNode;
    buttonType?: 'Normal' | 'Modal';
}

const ModalButton = ({children, buttonType = "Normal", ...otherProps}: ModalbuttonProps) => {
    return <AppButton className={`!font-semibold ${buttonType == 'Modal' ? 'w-full' : '!px-8'}`} {...otherProps}>
        {children}
    </AppButton>
}

export default ModalButton