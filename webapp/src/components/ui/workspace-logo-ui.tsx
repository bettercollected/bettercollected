import React from 'react';

import { useTranslation } from 'next-i18next';

import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';

import AuthAccountProfileImage from '../auth/account-profile-image';
import Button from './button';

interface IWorkspaceLogoProps {
    workspaceLogoRef: any;
    onChange: (e: any) => void;
    onClick: () => void;
    image?: string;
    profileName: string;
}
export default function WorkSpaceLogoUi({ workspaceLogoRef, onChange, onClick, image, profileName }: IWorkspaceLogoProps) {
    const { t } = useTranslation();
    return (
        <div className="flex md:flex-row flex-col gap-4 items-center">
            <AuthAccountProfileImage image={image} name={profileName} size={143} typography="h1" />
            <div className="flex flex-col justify-center md:items-start items-center">
                <p className="body3 mb-5 !text-black-700 md:text-start text-center">{t(localesCommon.imageSizeRestriction)}</p>
                <input data-testid="file-upload-profile" type="file" accept="image/*" className="hidden" ref={workspaceLogoRef} onChange={onChange} />
                <Button size="small" variant="ghost" className="!text-brand-500 hover:!bg-brand-200 !bg-white !border-brand-300" onClick={onClick}>
                    {t(buttonConstant.upload)}
                </Button>
            </div>
        </div>
    );
}
