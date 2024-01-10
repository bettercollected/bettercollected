import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
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

    const handleSubmit = (event: any) => {
        event.preventDefault();
        if (!isEmptyString(regex)) {
            handleRegex(regex, handleRegexType.ADD);
        }
    };

    return (
        <HeaderModalWrapper headerTitle={t('BUTTON.ADD_REGEX')}>
            <form onSubmit={handleSubmit}>
                <h4 className="h4-new">{t(groupConstant.regex.modal.title)}</h4>
                <p className="my-2">
                    <span className="!text-black-700 p2-new text-sm !font-normal">
                        Use <span className="text-pink-500">*@yourcompany.com</span> to add all employees with email addresses ending in &apos;@yourcompany.com&apos;.{' '}
                    </span>
                </p>
                <AppTextField onChange={handleInput} autoFocus placeholder="*@example.com">
                    {t(groupConstant.regex.modal.label)}
                </AppTextField>
                <div className="flex justify-end mt-4">
                    <AppButton size={ButtonSize.Medium} className={'w-full'} disabled={!regex}>
                        {t(buttonConstant.addRegex)}
                    </AppButton>
                </div>
            </form>
        </HeaderModalWrapper>
    );
}
