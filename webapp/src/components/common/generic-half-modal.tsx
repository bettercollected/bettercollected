import { ReactNode } from 'react';

import { useTranslation } from 'react-i18next';

import HeaderModalWrapper from '@Components/modals/modal-wrapper/header-modal-wrapper';
import { Button } from '@app/shadcn/components/ui/button';

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
                {/* The dismiss action is quiet — a filled near-black "No" carried
                    as much visual weight as the action itself and read like a
                    second primary. */}
                <Button className="flex-1" size="medium" onClick={closeModal} variant="v2Button">
                    {!negativeText ? t('BUTTON.CANCEL') : negativeText}
                </Button>
                <Button className="flex-1" size="medium" isLoading={loading} variant={type === 'danger' ? 'danger' : 'primary'} onClick={positiveAction}>
                    {type === 'danger' && !positiveText ? t('BUTTON.DELETE') : positiveText}
                </Button>
            </div>
        </HeaderModalWrapper>
    );
}