import React, { useRef } from 'react';

import { useTranslation } from 'next-i18next';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/button';
import { formConstant } from '@app/constants/locales/form';

import { InfoCircle } from '../icons/info-circle';

export default function RequestForDeletionView(props: any) {
    const { closeModal } = useModal();
    const { handleRequestForDeletion } = props;
    const { t } = useTranslation();

    const ref = useRef<HTMLDivElement>(null);

    return (
        <div ref={ref} className="relative m-auto w-full items-start justify-between rounded-lg bg-white">
            <div className="relative max-w-[465px] text-center flex flex-col items-center justify-between p-10">
                <InfoCircle className="mx-auto mb-6 text-gray-400 w-14 h-14 dark:text-gray-200" />
                <h3 className="mb-8 text-lg font-normal max-w-[352px] text-gray-500 dark:text-gray-400">{t(formConstant.deletionResponseWarningMessage)}</h3>
                <div className="flex items-center justify-between w-full">
                    <Button data-testid="logout-button" variant="solid" size="medium" color="danger" onClick={handleRequestForDeletion}>
                        {t(buttonConstant.yes)}
                    </Button>
                    <Button variant="solid" color="gray" size="medium" className="!bg-black-500 mr-2" onClick={closeModal}>
                        {t(buttonConstant.no)}
                    </Button>
                </div>
            </div>
            <Close onClick={() => closeModal()} className="cursor-pointer absolute top-3 right-3 h-auto w-3 text-gray-600 hover:text-black dark:text-white" />
        </div>
    );
}
