import React from 'react';

import { useTranslation } from 'next-i18next';

import { buttons, localesDefault, onBoarding } from '@app/constants/locales';

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
                <p className="body3 mb-5 !text-black-700 md:text-start text-center">{t(localesDefault.imageSizeRestriction)}</p>
                <input data-testid="file-upload-profile" type="file" accept="image/*" className="hidden" ref={workspaceLogoRef} onChange={onChange} />
                <Button size="small" variant="ghost" className="!text-brand-500 hover:!bg-brand-200 !bg-white !border-brand-300" onClick={onClick}>
                    {t(buttons.upload)}
                </Button>
            </div>
        </div>
    );
}
