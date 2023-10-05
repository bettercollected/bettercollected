import { ReactNode } from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import Divider from '@mui/material/Divider';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';


interface IModalWrapperProps {
    headerTitle?: string;
    title?: string;
    subTitle?: string;
    children?: ReactNode;
    type?: 'danger' | 'confirmation';
    positiveText?: string;
    negativeText?: string;
    positiveAction?: (e?: any) => void;
}

export default function GenericHalfModal({ headerTitle, title, subTitle, type, positiveAction, positiveText, negativeText = 'Cancel', children }: IModalWrapperProps) {
    const { closeModal } = useModal();
    return (
        <div className="flex flex-col bg-white rounded-md w-full min-w-[350px] max-w-[500px]">
            <div className="p-4 flex items-center justify-between">
                <span className="text-black-800 text-sm p2-new">{headerTitle}</span>
                <Close onClick={closeModal} />
            </div>
            <Divider />
            <div className="flex flex-col p-10 !pt-6">
                {title && <span className="text-black-800 h2-new font-semibold">{title}</span>}
                {subTitle && <span className="p2-new text-sm mt-2 text-black-700">{subTitle}</span>}
                {children}
                <div className="flex w-full gap-4 mt-6">
                    <AppButton className="flex-1" size={ButtonSize.Medium} onClick={closeModal} variant={ButtonVariant.Secondary}>
                        {negativeText}
                    </AppButton>
                    <AppButton className="flex-1" size={ButtonSize.Medium} variant={type === 'danger' ? ButtonVariant.Danger : ButtonVariant.Primary} onClick={positiveAction}>
                        {type === 'danger' && !positiveText ? 'Delete' : positiveText}
                    </AppButton>
                </div>
            </div>
        </div>
    );
}