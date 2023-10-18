import React, { useState } from 'react';

import Image from 'next/image';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { Close } from '@mui/icons-material';
import cn from 'classnames';
import { SetStateAction } from 'jotai';

import useFormBuilderAtom from '@app/Components/FormBuilder/builderAtom';
import Camera from '@app/components/icons/camera';
import { selectBuilderState, selectLogo } from '@app/store/form-builder/selectors';
import { useAppSelector } from '@app/store/hooks';

interface IFormLogoComponent {
    setIsLogoClicked: React.Dispatch<SetStateAction<boolean>>;
    className?: string;
    imagesRemoved?: any;
    setImagesRemoved?: any;
}

const FormLogoComponent = (props: IFormLogoComponent) => {
    // Props
    const { setIsLogoClicked, className, setImagesRemoved, imagesRemoved } = props;

    // State
    const [isAddLogoClicked, setIsAddLogoClicked] = useState(false);
    const [isUpdateButtonClicked, setIsUpdateButtonClicked] = useState(false);
    const [selectedImageURL, setSelectedImageURL] = useState<string | null>(null);

    // Hooks
    const { setLogoImage } = useFormBuilderAtom();
    const logo = useAppSelector(selectLogo);
    const onClickUpdateNewLogoButton = () => {
        setIsAddLogoClicked(true);
    };

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = event.target.files && event.target.files[0];

        if (selectedFile) {
            setSelectedImageURL(URL.createObjectURL(selectedFile));
            setIsUpdateButtonClicked(true);
            setIsAddLogoClicked(false);
            setLogoImage(selectedFile);
        }
    };

    const onClickRemoveLogoButton = () => {
        setIsLogoClicked(false);
        setLogoImage(null);
        setImagesRemoved &&
            setImagesRemoved({
                ...imagesRemoved,
                logo: true
            });
    };

    const onClickCloseIcon = () => {
        setIsAddLogoClicked(false);
    };
    return (
        <div className={`relative w-fit z-50 px-12 md:px-[89px] mt-3 mb-12 ${className}`}>
            <div className={cn('rounded-lg w-[100px] h-[100px] flex flex-col justify-center items-center gap-3 cursor-pointer hover:shadow-logoCard', !isUpdateButtonClicked && 'bg-black-800')} onClick={onClickUpdateNewLogoButton}>
                <input id="form_logo" type="file" hidden onChange={handleFileChange} />
                {selectedImageURL || logo ? <Image height={100} width={100} objectFit="cover" src={selectedImageURL || logo || ''} alt="logo" className="rounded-lg hover:bg-black-100" /> : <LogoItems />}
            </div>
            {isAddLogoClicked && <AddLogoOptions onClickCloseIcon={onClickCloseIcon} onClickRemoveLogoButton={onClickRemoveLogoButton} />}
        </div>
    );
};

export default FormLogoComponent;

function LogoItems() {
    return (
        <>
            <Camera />
            <h1 className="body6 !text-white">Add Logo</h1>
        </>
    );
}

function AddLogoOptions({ onClickCloseIcon, onClickRemoveLogoButton }: any) {
    return (
        <div className="flex flex-col absolute z-40 shadow-logoCard sm:h-[166px] sm:w-[330px] top-[116px] bg-white p-4 rounded-lg gap-2">
            <div className="flex justify-between !font-semibold mb-4">
                <h1 className="body1 text-black-900">Logo</h1>
                <Close onClick={onClickCloseIcon} className="top-2 right-2 cursor-pointer p-2 h-8 w-8" />
            </div>

            <label htmlFor="form_logo" className="w-full rounded py-3 px-4 h-[36px] body4 bg-black-900 font-semibold hover:opacity-80 flex justify-center items-center">
                <span className="text-black-100 text-xs sm:text-sm">Update New Logo</span>
            </label>
            <AppButton className="!text-black-900 font-semibold !bg-black-300 hover:!bg-black-400 " onClick={onClickRemoveLogoButton}>
                Remove Logo
            </AppButton>
        </div>
    );
}
