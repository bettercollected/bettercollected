import React from 'react';

import { useTranslation } from 'next-i18next';

import Plus from '@Components/Common/Icons/Common/Plus';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { Typography } from '@mui/material';

import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { handleRegexType } from '@app/models/enums/groupRegex';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { isEmptyString } from '@app/utils/stringUtils';


interface IRegexCardProps {
    handleRegex: (regex: string, type: handleRegexType) => void;
    regex?: string;
}

export default function RegexCard({ handleRegex, regex }: IRegexCardProps) {
    const { t } = useTranslation();
    const { openModal } = useModal();
    const isAdmin = useAppSelector(selectIsAdmin);

    return (
        <div>
            <div className="flex flex-col md:flex-row justify-between items-start  md:items-center">
                <p className="h4-new !font-medium">{t(groupConstant.regex.title)}</p>
            </div>
            <div className="border-y-black-200 border-y py-4 mt-4">
                <div className="flex justify-between">
                    <div>
                        <p className="body4 !text-black-700">{t(groupConstant.regex.description)}</p>
                        <p className="body4 !text-black-700">
                            Eg: johndoe@<span className=" underline underline-offset-[6px]">yourdomain.any</span>
                        </p>
                    </div>
                    {regex?.length === 0 && isAdmin && (
                        <AppButton variant={ButtonVariant.Ghost} icon={<Plus className="h-4 w-4" />} onClick={() => openModal('ADD_REGEX', { handleRegex: handleRegex })}>
                            {t(buttonConstant.addRegex)}
                        </AppButton>
                    )}
                </div>
                {!!regex && !isEmptyString(regex) && (
                    <>
                        <p className="body1 mt-7 mb-3">{t(localesCommon.added)}</p>
                        <div className="px-2 py-3 border-2 border-black-400  rounded flex items-center justify-between md:w-[400px] body4">
                            <Typography noWrap className="!text-black-800">
                                {regex}
                            </Typography>
                            {isAdmin && (
                                <span onClick={() => handleRegex(regex, handleRegexType.REMOVE)} className="text-red-500 cursor-pointer">
                                    {t(localesCommon.remove)}
                                </span>
                            )}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}