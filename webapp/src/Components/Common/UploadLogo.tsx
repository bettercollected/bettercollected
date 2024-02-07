import React, { useRef, useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';

import AppButton from '@Components/Common/Input/Button/AppButton';
import cn from 'classnames';

import Camera from '@app/components/icons/camera';
import { Close } from '@app/components/icons/close';

interface IUploadLogo {
    className?: string;
    logoImageUrl?: string;
    onUpload?: (file: File) => void;
    onRemove?: () => void;
    showRemove?: boolean;
}

const UploadLogo = ({ className, onUpload, onRemove, logoImageUrl, showRemove = true }: IUploadLogo) => {
    const [showDropdown, setShowDropdown] = useState(false);
    const [logoUrl, setLogoUrl] = useState<string | null>(null);
    const logoRef = useRef<HTMLInputElement | null>(null);
    const { t } = useTranslation();

    React.useEffect(() => {
        if (logoImageUrl) {
            setLogoUrl(logoImageUrl);
        }
    }, []);

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = event.target.files && event.target.files[0];
        if (selectedFile) {
            setLogoUrl(URL.createObjectURL(selectedFile));
            onUpload && onUpload(selectedFile);
        }
    };
    const onRemoveLogo = () => {
        setShowDropdown(false);
        setLogoUrl(null);
        if (logoRef.current) {
            logoRef.current.value = '';
        }
        onRemove && onRemove();
    };

    return (
        <div className={`relative z-50  ${className}`}>
            <div className={cn('rounded-lg w-[72px] h-[72px] flex flex-col justify-center items-center items-s gap-3 cursor-pointer hover:shadow-hover', logoUrl ? '' : 'bg-new-black-800')} onClick={() => setShowDropdown(!showDropdown)}>
                <input ref={logoRef} id="form_logo" type="file" hidden onChange={handleFileChange} />
                {logoUrl ? (
                    <Image height={72} width={72} objectFit="cover" src={logoUrl} alt="logo" className="rounded-lg hover:bg-black-100" />
                ) : (
                    <>
                        <Camera />
                        <h1 className="body6 !text-white">{t('WORKSPACE.SETTINGS.DETAILS.ADD_LOGO')}</h1>
                    </>
                )}
            </div>
            {showDropdown && (
                <div className="flex flex-col absolute z-40 shadow-logoCard h-auto w-full sm:w-[330px] top-[116px] bg-white p-4 rounded-lg gap-2">
                    <div className="flex justify-between !font-semibold mb-4">
                        <h1 className="body1 text-black-900">Logo</h1>
                        <Close
                            onClick={() => {
                                setShowDropdown(false);
                            }}
                            className="top-2 right-2 cursor-pointer p-2 h-8 w-8"
                        />
                    </div>
                    <label onClick={() => logoRef.current?.click()} className="w-full rounded py-3 px-4 h-[36px] body4 bg-black-900 font-semibold hover:opacity-80 flex justify-center items-center">
                        <span className="text-black-100 text-xs sm:text-sm">{t('LOGO.UPDATE')}</span>
                    </label>
                    {showRemove && (
                        <AppButton className="!text-black-900 font-semibold !bg-black-300 hover:!bg-black-400 " onClick={onRemoveLogo}>
                            {t('LOGO.REMOVE')}
                        </AppButton>
                    )}
                </div>
            )}
        </div>
    );
};

export default UploadLogo;
