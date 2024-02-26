import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import ModalButton from '@Components/Common/Input/Button/ModalButton';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';


interface IVisibilityConfirmationModalViewProps {
    visibilityType: string;
    handleOnConfirm: () => void;
    isTemplate?: boolean;
}

const VisibilityConfirmationModalView = ({ visibilityType, handleOnConfirm, isTemplate = false }: IVisibilityConfirmationModalViewProps) => {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const title: any = {
        Public: [`${t('VISIBILITY_MODAL.ARE_YOU_SURE')} ${isTemplate ? t('VISIBILITY_MODAL.TEMPLATE.TITLE') : t('VISIBILITY_MODAL.FORM.TITLE')} `, t('PUBLIC')],
        Private: [`${t('VISIBILITY_MODAL.ARE_YOU_SURE')} ${isTemplate ? t('VISIBILITY_MODAL.TEMPLATE.TITLE') : t('VISIBILITY_MODAL.FORM.TITLE')} `, t('HIDDEN')],
        Group: [t('VISIBILITY_MODAL.GROUP.TITLE'), '']
    };
    const description: any = {
        Public: isTemplate ? t('VISIBILITY_MODAL.TEMPLATE.DESCRIPTION_PUBLIC') : t('VISIBILITY_MODAL.FORM.DESCRIPTION_PUBLIC'),
        Private: isTemplate ? t('VISIBILITY_MODAL.TEMPLATE.DESCRIPTION_PRIVATE') : t('VISIBILITY_MODAL.FORM.DESCRIPTION_PRIVATE'),
        Group: t('VISIBILITY_MODAL.GROUP.TITLE')
    };

    const onClickConfirm = () => {
        handleOnConfirm();
        closeModal();
    };

    return (
        <div className={'md:w-[466px] rounded-xl bg-white'}>
            <div className={'flex justify-between p-4'}>
                <h1 className={'text-sm font-normal text-black-800'}>{t('VISIBILITY_MODAL.TITLE')}</h1>
                <div className={'absolute top-3 right-5 cursor-pointer hover:bg-black-200 hover:rounded-sm p-1'}>
                    <Close
                        onClick={() => {
                            closeModal();
                        }}
                    />
                </div>
            </div>
            <Divider />
            <div className={'pt-6 p-10 flex flex-col gap-3'}>
                <h1 className={'h4-new !text-black-800'}>
                    {title[visibilityType][0]} <span className={'text-pink-500'}>{title[visibilityType][1]} </span> {title[visibilityType][1] ? '?' : '.'}
                </h1>
                <h2 className={'text-sm font-normal mb-3 text-black-700'}>{description[visibilityType]}</h2>
                <div className={'flex flex-row gap-4 w-full'}>
                    <ModalButton buttonType={'Modal'} size={ButtonSize.Medium} variant={ButtonVariant.Secondary} onClick={closeModal}>
                        {t('BUTTON.CANCEL')}
                    </ModalButton>
                    <ModalButton buttonType={'Modal'} size={ButtonSize.Medium} onClick={onClickConfirm}>
                        {t('BUTTON.CONFIRM')}
                    </ModalButton>
                </div>
            </div>
        </div>
    );
};

export default VisibilityConfirmationModalView;