import React from 'react';

import {useTranslation} from 'next-i18next';

import {Close} from '@app/components/icons/close';
import {useModal} from '@app/components/modal-views/context';
import {buttonConstant} from '@app/constants/locales/button';
import {localesCommon} from '@app/constants/locales/common';
import {ButtonSize, ButtonVariant} from '@Components/Common/Input/Button/AppButtonProps';
import ModalButton from "@Components/Common/Input/Button/ModalButton";

interface IDeleteConfirmationModla {
    title: string;
    handleDelete: () => void;
}

export default function DeleteConfirmationModal({title, handleDelete}: IDeleteConfirmationModla) {
    const {t} = useTranslation();
    const {closeModal} = useModal();
    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]">
            <div className="rounded-[4px] relative m-auto max-w-[500px] items-start justify-between bg-white">
                <div className="relative flex flex-col items-start justify-start p-10">
                    <div>
                        <h4 className="sh1 mb-6">{title} ?</h4>
                        <p className="!text-black-600 mb-8 body4 leading-none">{t(localesCommon.deleteMessage)}</p>
                    </div>
                    <div className="flex w-full gap-2 justify-between">
                        <ModalButton buttonType={"Modal"} size={ButtonSize.Medium} data-testid="logout-button" variant={ButtonVariant.Danger} onClick={handleDelete}>
                            {title.split(' ')[0]}
                        </ModalButton>
                        <ModalButton buttonType={"Modal"} size={ButtonSize.Medium} variant={ButtonVariant.Secondary}  onClick={() => closeModal()}>
                            {t(buttonConstant.cancel)}
                        </ModalButton>
                    </div>
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black"
                     onClick={() => closeModal()}>
                    <Close className="h-auto w-3 text-gray-600 dark:text-white"/>
                </div>
            </div>
        </div>
    );
}
