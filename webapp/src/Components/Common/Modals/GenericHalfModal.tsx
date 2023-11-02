import React, { ReactNode } from 'react';

import { useTranslation } from 'next-i18next';

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

export default function GenericHalfModal({ headerTitle, title, subTitle, type, positiveAction, positiveText, negativeText, children }: IModalWrapperProps) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    return (
        <div className="flex flex-col bg-white rounded-md w-full min-w-[350px] max-w-[500px]">
            <div className="p-4 flex items-center justify-between">
                <span className="text-black-800 text-sm p2-new">{headerTitle}</span>
                <div className={'absolute top-3 right-5 cursor-pointer hover:bg-black-200 hover:rounded-sm p-1'}>
                    <Close
                        onClick={() => {
                            closeModal();
                        }}
                    />
                </div>
            </div>
            <Divider />
            <div className="flex flex-col p-10 !pt-6">
                {title && <span className="text-black-800 text-base font-semibold">{title}</span>}
                {subTitle && <span className="p2-new text-sm mt-2 text-black-700">{subTitle}</span>}
                {children}
                <div className="flex w-full gap-4 mt-6">
                    <AppButton className="flex-1" size={ButtonSize.Medium} onClick={closeModal} variant={ButtonVariant.Secondary}>
                        {positiveText ? t('BUTTON.CANCEL') : negativeText}
                    </AppButton>
                    <AppButton className="flex-1" size={ButtonSize.Medium} variant={type === 'danger' ? ButtonVariant.Danger : ButtonVariant.Primary} onClick={positiveAction}>
                        {type === 'danger' && !positiveText ? t('BUTTON.DELETE') : positiveText}
                    </AppButton>
                </div>
            </div>
        </div>
    );
}
