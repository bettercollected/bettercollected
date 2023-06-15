import React from 'react';

import { useTranslation } from 'next-i18next';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';

interface IDeleteConfirmationModla {
    title: string;
    handleDelete: () => void;
}
export default function DeleteConfirmationModal({ title, handleDelete }: IDeleteConfirmationModla) {
    const { t } = useTranslation();
    const { closeModal } = useModal();
    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]">
            <div className="rounded-[4px] relative m-auto max-w-[500px] items-start justify-between bg-white">
                <div className="relative flex flex-col items-start justify-start p-10">
                    <div>
                        <h4 className="sh1 mb-6">{title} ?</h4>
                        <p className="!text-black-600 mb-8 body4 leading-none">{t(localesCommon.deleteMessage)}</p>
                    </div>
                    <div className="flex w-full gap-4 justify-between">
                        <Button className="flex-1 body4" data-testid="logout-button" variant="solid" size="medium" color="danger" onClick={handleDelete}>
                            {t(buttonConstant.delete)}
                        </Button>
                        <Button variant="solid" color="gray" size="medium" className="flex-1 body4 !bg-black-500" onClick={() => closeModal()}>
                            {t(buttonConstant.cancel)}
                        </Button>
                    </div>
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={() => closeModal()}>
                    <Close className="h-auto w-3 text-gray-600 dark:text-white" />
                </div>
            </div>
        </div>
    );
}
