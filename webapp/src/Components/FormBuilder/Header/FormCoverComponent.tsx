import React, { useRef, useState } from 'react';

import Image from 'next/image';

import cn from 'classnames';
import html2canvas from 'html2canvas';
import { SetStateAction } from 'jotai';
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch';

import Upload from '@app/components/icons/upload';
import Button from '@app/components/ui/button';

interface IFormCoverComponent {
    setIsCoverClicked: React.Dispatch<SetStateAction<boolean>>;
}

const FormCoverComponent = (props: IFormCoverComponent) => {
    const { setIsCoverClicked } = props;
    const [imageURL, setImageURL] = useState<string>('');
    const [showButtonsOnHOver, setShowButtonsOnHOver] = useState(false);
    const [isSaveButtonClicked, setIsSaveButtonClicked] = useState(false);
    const inputRef = useRef<HTMLInputElement | null>(null);

    const handleFileChange = (event: any) => {
        if (!event.target.files.length) return;
        setImageURL(URL.createObjectURL(event.target.files[0]));
        isSaveButtonClicked && setIsSaveButtonClicked(false);
    };

    const handleOnMouseEnter = (event: any) => {
        setShowButtonsOnHOver(true);
    };
    const handleOnMouseLeave = (event: any) => {
        setShowButtonsOnHOver(false);
    };

    const onClickRemoveButton = () => {
        setIsCoverClicked(false);
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
                // const formData = new FormData();
                // formData.append('banner_image', file);
            });
        });
    };

    const onClickUpdateButton = () => {
        inputRef.current?.click();
        if (inputRef.current) {
            inputRef.current.value = '';
        }
    };

    return (
        <div className="w-full aspect-banner-mobile lg:aspect-banner-desktop bg-blue-300 hover:bg-blue-400 my-0 flex justify-center items-center text-black-900 overflow-hidden">
            <input type="file" id="form_banner" ref={inputRef} accept="image/*" hidden onChange={handleFileChange} />
            {imageURL ? (
                <div className="relative z-0 w-full aspect-banner-mobile lg:aspect-banner-desktop" onMouseEnter={handleOnMouseEnter} onMouseLeave={handleOnMouseLeave}>
                    {isSaveButtonClicked ? (
                        <>
                            <Image layout="fill" objectFit="cover" src={imageURL} alt="test" className={cn(showButtonsOnHOver && 'brightness-75')} />
                            {showButtonsOnHOver && <HoveredButtons onClickUpdateButton={onClickUpdateButton} onClickRemoveButton={onClickRemoveButton} />}
                        </>
                    ) : (
                        <DragImagePositionComponent imageURL={imageURL} showButtonsOnHOver={showButtonsOnHOver} onClickCancelButton={onClickCancelButton} onClickSaveButton={onClickSaveButton} />
                    )}
                </div>
            ) : (
                <EmptyCoverItems onClickUpdateButton={onClickUpdateButton} />
            )}
        </div>
    );
};

export default FormCoverComponent;

const HoveredButtons = ({ onClickUpdateButton, onClickRemoveButton }: any) => {
    return (
        <div className="absolute z-10 bottom-6 right-8 cursor-pointer flex gap-4 justify-end font-semibold  text-black-100">
            <Button size="small" className="!text-black-900 !font-semibold hover:opacity-80 !bg-black-100 focus:!ring-0" onClick={onClickRemoveButton}>
                Remove Cover
            </Button>
            <Button size="small" className="!font-semibold hover:opacity-80 !bg-black-900 focus:!ring-0" onClick={onClickUpdateButton}>
                <span className="text-black-100 text-xs sm:text-sm">Update New Cover</span>
            </Button>
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
                                maxWidth: '100vw',
                                height: '100%',
                                width: '100vw',
                                cursor: 'grabbing'
                            }}
                        >
                            <img style={{ width: '100vw', height: '100vh', objectFit: 'cover' }} src={imageURL} alt="test" className={cn(showButtonsOnHOver && 'brightness-75 aspect-banner-mobile lg:aspect-banner-desktop')} />
                        </TransformComponent>
                    );
                }}
            </TransformWrapper>

            <div className="flex justify-center items-center">
                <span className="absolute top-1/2 z-10 w-fit h-fit body4 !text-white cursor-pointer !font-semibold py-2 px-4 bg-black-700 rounded opacity-80">Drag Image To Reposition</span>
            </div>

            <div className="absolute z-10 bottom-6 right-8 cursor-pointer flex gap-4 justify-end font-semibold  text-black-100">
                <Button size="small" className=" w-[109px] !text-black-900 !font-semibold hover:opacity-80 !bg-black-100 focus:!ring-0" onClick={onClickCancelButton}>
                    Cancel
                </Button>
                <Button size="small" className="w-[109px] !font-semibold hover:opacity-80 !bg-black-900 focus:!ring-0" onClick={onClickSaveButton}>
                    Save Cover
                </Button>
            </div>
        </>
    );
};

const EmptyCoverItems = ({ onClickUpdateButton }: { onClickUpdateButton: () => void }) => {
    return (
        <div className="flex flex-col items-center" onClick={onClickUpdateButton}>
            <Upload />
            <h1 className="body1 !font-semibold">Upload Banner Image</h1>
            <h1 className="body4">5:1 aspect ratio recommended</h1>
        </div>
    );
};
