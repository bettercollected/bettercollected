import React from 'react';

import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';

import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';

import AuthAccountProfileImage from '../auth/account-profile-image';


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
                <AppButton variant={ButtonVariant.Ghost} onClick={onClick}>
                    {t(buttonConstant.upload)}
                </AppButton>
            </div>
        </div>
    );
}