import React, { useState } from 'react';

import Image from 'next/image';

import { Close } from '@mui/icons-material';
import cn from 'classnames';

import Camera from '@app/components/icons/camera';
import Button from '@app/components/ui/button';

interface IUploadLogo {
    className?: string;
    onUpload?: (file: File) => void;
    onRemove?: () => void;
}

const UploadLogo = ({ className, onUpload, onRemove }: IUploadLogo) => {
    const [showDropdown, setShowDropdown] = useState(false);
    const [logoUrl, setLogoUrl] = useState<string | null>(null);

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
        onRemove && onRemove();
    };

    return (
        <div className={`relative z-50  ${className}`}>
            <div className={cn('rounded-lg w-[100px] h-[100px] flex flex-col justify-center items-center items-s gap-3 cursor-pointer hover:shadow-logoCard bg-new-black-800')} onClick={() => setShowDropdown(!showDropdown)}>
                <input id="form_logo" type="file" hidden onChange={handleFileChange} />
                {logoUrl ? (
                    <Image height={100} width={100} objectFit="cover" src={logoUrl} alt="logo" className="rounded-lg hover:bg-black-100" />
                ) : (
                    <>
                        <Camera />
                        <h1 className="body6 !text-white">Add Logo</h1>
                    </>
                )}
            </div>
            {showDropdown && (
                <div className="flex flex-col absolute z-40 shadow-logoCard sm:h-[166px] sm:w-[330px] top-[116px] bg-white p-4 rounded-lg gap-2">
                    <div className="flex justify-between !font-semibold mb-4">
                        <h1 className="body1 text-black-900">Logo</h1>
                        <Close
                            onClick={() => {
                                setShowDropdown(false);
                            }}
                            className="top-2 right-2 cursor-pointer p-2 h-8 w-8"
                        />
                    </div>

                    <label htmlFor="form_logo" className="w-full rounded py-3 px-4 h-[36px] body4 bg-black-900 font-semibold hover:opacity-80 flex justify-center items-center">
                        <span className="text-black-100 text-xs sm:text-sm">Update New Logo</span>
                    </label>
                    <Button size="small" className="!text-black-900 font-semibold !bg-black-300 hover:bg-black-400 focus:!ring-0" onClick={onRemoveLogo}>
                        Remove Logo
                    </Button>
                </div>
            )}
        </div>
    );
};

export default UploadLogo;
