import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import BetterInput from '@app/components/Common/input';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button/button';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { handleRegexType } from '@app/models/enums/groupRegex';
import { isEmptyString } from '@app/utils/stringUtils';

export default function AddRegexModal({ handleRegex }: { handleRegex: (regex: string, type: handleRegexType) => void }) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const [regex, setRegex] = useState<string>('');
    const handleInput = (event: any) => {
        setRegex(event.target.value);
    };

    const handleSubmit = (e: any) => {
        if (!isEmptyString(regex)) {
            handleRegex(regex, handleRegexType.ADD);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="p-10 relative bg-brand-100 md:w-[658px] rounded-[8px]">
            <Close onClick={closeModal} className="absolute top-2 right-2 cursor-pointer p-2 h-8 w-8" />
            <h4 className="h4">{t(groupConstant.regex.modal.title)}</h4>
            <p className="mt-3 mb-10 body6">
                <span>{t(localesCommon.example)} </span>
                <span className="!text-black-700 !font-normal">{t(groupConstant.regex.modal.description)}</span>
            </p>
            <BetterInput onChange={handleInput} label={t(groupConstant.regex.modal.label)} placeholder="*@example.com"></BetterInput>
            <div className="flex justify-end">
                <Button size="medium" className="body1" disabled={!regex}>
                    {t(buttonConstant.addRegex)}
                </Button>
            </div>
        </form>
    );
}
