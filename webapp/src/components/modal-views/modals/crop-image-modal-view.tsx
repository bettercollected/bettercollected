import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import cn from 'classnames';
import AvatarEditor from 'react-avatar-editor';

import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';


interface ICropImageModalViewProps {
    profileEditorRef: React.LegacyRef<AvatarEditor> | undefined;
    uploadImage: string | File;
    profileInputRef: any;
    modalIndex: number;
    closeModal: () => void;
    onSave: (e: any) => void;
}

export default function CropImageModalView({ profileEditorRef, uploadImage, closeModal, onSave, modalIndex }: ICropImageModalViewProps) {
    const [scale, setScale] = useState(1);
    const { t } = useTranslation();
    const [isLoading, setLoading] = useState(false);
    return (
        <div className={cn(' flex justify-center items-center', modalIndex === 2 && 'h-screen w-screen')}>
            <div className="p-4 bg-white flex flex-col items-center rounded-[8px] max-w-[420px] max-h-[500px] ">
                <h1 className="font-bold text-lg mb-2">{t(localesCommon.updateYourProfileImage)}</h1>
                <AvatarEditor crossOrigin="anonymous" ref={profileEditorRef} image={uploadImage} width={250} height={250} border={50} borderRadius={16} color={[0, 0, 0, 0.6]} scale={scale} rotate={0} />
                <div className="flex mb-2 gap-1 text-3xl text-gray-600 justify-center items-center">
                    <span>-</span>
                    <input name="scale" type="range" onChange={(e) => setScale(parseFloat(e.target.value))} min={1} max={4} step="0.01" defaultValue={1} />
                    <span>+</span>
                </div>
                <div className="flex gap-2 justify-around w-full">
                    <AppButton
                        data-testid="save-button"
                        isLoading={isLoading}
                        className="w-full"
                        disabled={!uploadImage}
                        onClick={(e) => {
                            onSave(e);
                            setLoading(true);
                        }}
                    >
                        {t(buttonConstant.saveImage)}
                    </AppButton>
                    <AppButton  disabled={isLoading} variant={ButtonVariant.Secondary}  className="w-full" onClick={closeModal}>
                        {t(buttonConstant.cancel)}
                    </AppButton>
                </div>
            </div>
        </div>
    );
}