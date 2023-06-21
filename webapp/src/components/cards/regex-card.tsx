import React from 'react';

import { useTranslation } from 'next-i18next';

import Plus from '@Components/Common/Icons/Plus';
import { Typography } from '@mui/material';

import { buttonConstant } from '@app/constants/locales/button';
import { groupConstant } from '@app/constants/locales/group';

export default function RegexCard({ addRegex }: { addRegex: () => void }) {
    const { t } = useTranslation();
    return (
        <div className=" p-6 bg-white  rounded">
            <div className="flex justify-between items-center">
                <p className="body1">{t(groupConstant.regex.title)}</p>
                <div onClick={addRegex} className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                    <Plus className="h-4 w-4" />
                    <Typography className="!text-brand-500  body6">{t(buttonConstant.addRegex)}</Typography>
                </div>
            </div>
            <p className="body4 !text-black-700">{t(groupConstant.regex.description)}</p>
            <p className="body4 !text-black-700">{t(groupConstant.regex.example)}</p>
        </div>
    );
}
