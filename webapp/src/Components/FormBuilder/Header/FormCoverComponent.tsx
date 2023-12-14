import React, { useRef, useState } from 'react';

import Image from 'next/image';

import useFormBuilderAtom from '@Components/FormBuilder/builderAtom';
import cn from 'classnames';
import html2canvas from 'html2canvas';
import { SetStateAction } from 'jotai';
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch';

import Upload from '@app/components/icons/upload';
import { selectBuilderState, selectCoverImage } from '@app/store/form-builder/selectors';
import { IBuilderState } from '@app/store/form-builder/types';
import { useAppSelector } from '@app/store/hooks';

interface IFormCoverComponent {
    setIsCoverClicked: React.Dispatch<SetStateAction<boolean>>;
    imagesRemoved: any;
    setImagesRemoved: any;
}

const FormCoverComponent = (props: IFormCoverComponent) => {
    // Props
    const { setIsCoverClicked, imagesRemoved, setImagesRemoved } = props;

    // State
    const [imageURL, setImageURL] = useState<string>('');
    const [showButtonsOnHover, setShowButtonsOnHover] = useState(false);
    const [isSaveButtonClicked, setIsSaveButtonClicked] = useState(false);

    // Ref
    const inputRef = useRef<HTMLInputElement | null>(null);

    // Hooks
    const { setCoverImage } = useFormBuilderAtom();
    const coverImage = useAppSelector(selectCoverImage);

    const handleFileChange = (event: any) => {
        if (!event.target.files.length) return;
        setImageURL(URL.createObjectURL(event.target.files[0]));
        setIsSaveButtonClicked(false);
    };

    const handleOnMouseEnter = (event: any) => {
        setShowButtonsOnHover(true);
    };
    const handleOnMouseLeave = (event: any) => {
        setShowButtonsOnHover(false);
    };

    const onClickRemoveButton = () => {
        setIsCoverClicked(false);
        setCoverImage(null);
        setImagesRemoved({
            ...imagesRemoved,
            cover: true
        });
    };

    const onClickCancelButton = () => {
        setImageURL('');
        if (inputRef.current) {
            inputRef.current.value = '';
        }
    };

    const onClickSaveButton = () => {
        const croppedImageDiv: any = document.getElementsByClassName('react-transform-wrapper')[0];
        if (!croppedImageDiv) return;
        html2canvas(croppedImageDiv).then((canvas: HTMLCanvasElement) => {
            canvas.toBlob(async (blob: any) => {
                const file = new File([blob], 'formbannerimage.png', { type: blob.type });
                setImageURL(URL.createObjectURL(file));
                setIsSaveButtonClicked(true);
                setCoverImage(file);
            });
        });
    };

    const onClickUpdateButton = () => {
        inputRef.current?.click();
        if (inputRef.current) {
            inputRef.current.value = '';
        }
    };

    const getImageComponent = (url: string) => {
        return (
            <>
                <Image layout="fill" objectFit="cover" src={url} alt="test" objectPosition="center" className={cn(showButtonsOnHover && 'brightness-75')} />
                {showButtonsOnHover && <HoveredButtons onClickUpdateButton={onClickUpdateButton} onClickRemoveButton={onClickRemoveButton} />}
            </>
        );
    };

    return (
        <div className="w-full  aspect-banner-mobile lg:aspect-banner-desktop bg-new-blue-200 hover:bg-new-blue-300 my-0 flex justify-center items-center text-black-900 overflow-hidden">
            <input type="file" id="form_banner" ref={inputRef} accept="image/*" hidden onChange={handleFileChange} />
            {imageURL ? (
                <div className="relative z-0 w-full  aspect-banner-mobile lg:aspect-banner-desktop" onMouseEnter={handleOnMouseEnter} onMouseLeave={handleOnMouseLeave}>
                    {isSaveButtonClicked ? getImageComponent(imageURL) : <DragImagePositionComponent imageURL={imageURL} showButtonsOnHOver={showButtonsOnHover} onClickCancelButton={onClickCancelButton} onClickSaveButton={onClickSaveButton} />}
                </div>
            ) : (
                <>
                    {coverImage ? (
                        <div className="relative z-0 w-full aspect-banner-mobile lg:aspect-banner-desktop" onMouseEnter={handleOnMouseEnter} onMouseLeave={handleOnMouseLeave}>
                            {getImageComponent(coverImage || '')}
                        </div>
                    ) : (
                        <EmptyCoverItems onClickUpdateButton={onClickUpdateButton} onClickRemoveButton={onClickRemoveButton} />
                    )}
                </>
            )}
        </div>
    );
};

export default FormCoverComponent;

const HoveredButtons = ({ onClickUpdateButton, onClickRemoveButton }: any) => {
    return (
        <div className="absolute z-10 bottom-6 right-6 cursor-pointer flex gap-2 justify-end font-semibold  text-black-100">
            {onClickRemoveButton && (
                <button className="px-2 py-1 text-xs sm:text-sm rounded !text-black-900 !font-semibold hover:opacity-80 !bg-black-100 focus:!ring-0" onClick={onClickRemoveButton}>
                    Remove Cover
                </button>
            )}
            {onClickUpdateButton && (
                <button className="px-2 py-1 rounded text-xs sm:text-sm !font-semibold text-black-100 hover:opacity-80 !bg-black-900 focus:!ring-0" onClick={onClickUpdateButton}>
                    Update New Cover
                </button>
            )}
        </div>
    );
};

const DragImagePositionComponent = ({ imageURL, showButtonsOnHOver, onClickCancelButton, onClickSaveButton }: any) => {
    const transformComponentRef = useRef(null);
    return (
        <>
            <TransformWrapper centerOnInit ref={transformComponentRef}>
                {({ resetTransform }) => {
                    return (
                        <TransformComponent
                            wrapperStyle={{
                                maxHeight: '100%',
                                maxWidth: '100%',
                                height: '100%',
                                width: '100%',
                                cursor: 'grabbing'
                            }}
                        >
                            <img style={{ width: '100vw', height: '100vh', objectFit: 'fill' }} src={imageURL} alt="test" className={cn(showButtonsOnHOver && 'brightness-75 aspect-banner-mobile lg:aspect-banner-desktop')} />
                        </TransformComponent>
                    );
                }}
            </TransformWrapper>

            <div className="flex justify-center items-center pointer-events-none">
                <span className="absolute z-[10000] top-1/3 md:top-1/2 w-fit h-fit body4 !text-white cursor-pointer mb-10 md:md-0 !font-semibold py-2 px-4 bg-black-700 rounded opacity-80">Drag Image To Reposition</span>
            </div>

            <div className="absolute bottom-6 right-8 cursor-pointer flex gap-4 justify-end font-semibold  text-black-100 !z-[100]">
                <button className=" px-2 py-1 text-sm rounded !text-black-900 !font-semibold hover:opacity-80 !bg-black-100 focus:!ring-0" onClick={onClickCancelButton}>
                    Cancel
                </button>
                <button className="px-2 py-1 text-sm rounded !font-semibold hover:opacity-80 !bg-black-900 focus:!ring-0" onClick={onClickSaveButton}>
                    Save Cover
                </button>
            </div>
        </>
    );
};

const EmptyCoverItems = ({ onClickUpdateButton, onClickRemoveButton }: { onClickUpdateButton: () => void; onClickRemoveButton: () => void }) => {
    return (
        <div className="relative w-full h-full">
            <div className="flex flex-col items-center justify-center h-full">
                <div className="flex flex-col items-center cursor-pointer mb-10 md:mb-0" onClick={onClickUpdateButton}>
                    <Upload className="w-[32px] h-[32px] md:w-[62px] md:h-[62px]" />
                    <h1 className="text-sm md:body1 !font-semibold">Upload Banner Image</h1>
                    <h1 className="text-xs md:body4">5:1 aspect ratio recommended</h1>
                </div>
            </div>
            {onClickRemoveButton && (
                <div className="absolute z-10 bottom-6 right-8 ">
                    <div className="z-[1000] !text-black-900 text-[12px] px-2 py-1 rounded !font-semibold hover:opacity-80 !bg-black-100 focus:!ring-0 cursor-pointer" onClick={onClickRemoveButton}>
                        Remove Cover
                    </div>
                </div>
            )}
        </div>
    );
};
