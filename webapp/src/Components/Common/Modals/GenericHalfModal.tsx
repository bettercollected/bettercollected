import React, { ReactNode } from 'react';

import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';

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
    loading?: boolean;
}

export default function GenericHalfModal({ headerTitle, title, subTitle, type, positiveAction, positiveText, negativeText, loading, children }: IModalWrapperProps) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    return (
        <HeaderModalWrapper headerTitle={headerTitle}>
            {title && <span className="text-black-800 text-base font-semibold">{title}</span>}
            {subTitle && <span className="p2-new text-sm mt-2 text-black-700">{subTitle}</span>}
            {children}
            <div className="flex w-full gap-4 mt-6">
                <AppButton className="flex-1" size={ButtonSize.Medium} onClick={closeModal} variant={ButtonVariant.Secondary}>
                    {!negativeText ? t('BUTTON.CANCEL') : negativeText}
                </AppButton>
                <AppButton className="flex-1" size={ButtonSize.Medium} isLoading={loading} variant={type === 'danger' ? ButtonVariant.Danger : ButtonVariant.Primary} onClick={positiveAction}>
                    {type === 'danger' && !positiveText ? t('BUTTON.DELETE') : positiveText}
                </AppButton>
            </div>
        </HeaderModalWrapper>
    );
}