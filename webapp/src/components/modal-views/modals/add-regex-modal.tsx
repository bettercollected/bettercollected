import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { handleRegexType } from '@app/models/enums/groupRegex';
import { isEmptyString } from '@app/utils/stringUtils';
import AppButton from "@Components/Common/Input/Button/AppButton";
import AppTextField from "@Components/Common/Input/AppTextField";
import {ButtonSize} from "@Components/Common/Input/Button/AppButtonProps";

export default function AddRegexModal({ handleRegex }: { handleRegex: (regex: string, type: handleRegexType) => void }) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const [regex, setRegex] = useState<string>('');
    const handleInput = (event: any) => {
        setRegex(event.target.value);
    };

    const handleSubmit = (event: any) => {
        event.preventDefault();
        if (!isEmptyString(regex)) {
            handleRegex(regex, handleRegexType.ADD);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="p-10 relative bg-brand-100 md:w-[600px] rounded-[8px]">
            <Close onClick={closeModal} className="absolute top-2 right-2 cursor-pointer p-2 h-8 w-8" />
            <h4 className="h4">{t(groupConstant.regex.modal.title)}</h4>
            <p className="mt-3 mb-10 body6">
                <span>{t(localesCommon.example)} </span>
                <span className="!text-black-700 !font-normal">{t(groupConstant.regex.modal.description)}</span>
            </p>
            <AppTextField  onChange={handleInput} placeholder="*@example.com">
                {t(groupConstant.regex.modal.label)}
            </AppTextField>
            <div className="flex justify-end mt-4">
                <AppButton size={ButtonSize.Medium} className={'w-full'} disabled={!regex}>
                    {t(buttonConstant.addRegex)}
                </AppButton>
            </div>
        </form>
    );
}
