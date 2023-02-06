import React, { useRef } from 'react';
import { useState } from 'react';

import { useRouter } from 'next/router';

import ModeEditIcon from '@mui/icons-material/ModeEdit';
import SaveIcon from '@mui/icons-material/Save';
import { CircularProgress } from '@mui/material';
import html2canvas from 'html2canvas';
import { toast } from 'react-toastify';
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch';

import Image from '@app/components/ui/image';
import { ToastId } from '@app/constants/toastId';
import { BannerImageComponentPropType } from '@app/containers/dashboard/WorkspaceHomeContainer';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';

export default function BannerImageComponent(props: BannerImageComponentPropType) {
    const { workspace, isFormCreator } = props;
    const router = useRouter();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const [bannerImage, setBannerImage] = useState('');
    const bannerImageInputRef = useRef<HTMLInputElement>(null);

    const onuploadFileChange = (e: any) => {
        if (!e.target.files.length) return;
        setBannerImage(URL.createObjectURL(e.target.files[0]));
    };

    const onClickFileUploadButton = () => {
        if (!!bannerImageInputRef.current) {
            bannerImageInputRef.current.click();
        }
    };

    const onClickFileSaveButton = (e: any) => {
        const croppedImageDiv: any = document.getElementsByClassName('react-transform-wrapper')[0];
        if (!croppedImageDiv) return;
        html2canvas(croppedImageDiv).then((canvas: HTMLCanvasElement) => {
            canvas.toBlob(async (blob: any) => {
                const file = new File([blob], 'bannerimage.png', { type: blob.type });
                const formData = new FormData();
                formData.append('banner_image', file);
                const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
                if (response.error) {
                    toast('Something went wrong', { toastId: ToastId.ERROR_TOAST });
                }
                if (response.data) {
                    toast('Workspace Updated', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
                    setBannerImage('');
                    router.push(router.asPath, undefined);
                }
            });
        });
    };

    function ConditionalImageRendering() {
        switch (!!bannerImage) {
            case false:
                return <Image src={workspace.bannerImage} priority layout="fill" objectFit="contain" objectPosition="center" alt={workspace?.title} />;
            case true:
                return (
                    <TransformWrapper centerOnInit>
                        <TransformComponent wrapperStyle={{ maxHeight: 'calc(100vh)', maxWidth: '100%', height: '100%', width: '100%' }}>
                            <img src={bannerImage} alt="test" />
                        </TransformComponent>
                    </TransformWrapper>
                );
            default:
                return <></>;
        }
    }

    const timeStamp = new Date().getTime();

    return (
        <div className="relative overflow-hidden h-44 w-full md:h-80 xl:h-[380px] bannerdiv">
            {!!bannerImage ? (
                <TransformWrapper centerOnInit>
                    <TransformComponent wrapperStyle={{ maxHeight: 'calc(100vh)', maxWidth: '100%', height: '100%', width: '100%' }}>
                        <img src={bannerImage} alt="test" />
                    </TransformComponent>
                </TransformWrapper>
            ) : (
                <Image src={workspace.bannerImage + '?' + timeStamp} priority layout="fill" objectFit="contain" objectPosition="center" alt={workspace?.title} />
            )}
            {isFormCreator() && (
                <div className={`absolute bottom-2 right-4 hidden ${!!bannerImage ? '!block' : 'editbannerdiv'}`}>
                    <div className="flex justify-between">
                        {!isLoading && (
                            <div className="p-2 ml-2 my-19 !bg-blue-600 hover:bg-blue-700 cursor-pointer rounded-md" onClick={onClickFileUploadButton}>
                                <ModeEditIcon className="!w-5 !h-5 text-white" />
                                <span className="ml-1 text-white">update image</span>
                            </div>
                        )}
                        {!!bannerImage && (
                            <div
                                style={{ pointerEvents: isLoading ? 'none' : 'auto' }}
                                className={`p-2 ml-2 ${isLoading ? 'bg-gray-500' : '!bg-blue-600'} my-19 flex justify-center items-center  hover:bg-blue-700 cursor-pointer rounded-md`}
                                onClick={onClickFileSaveButton}
                            >
                                {!isLoading ? <SaveIcon className="!w-5 !h-5 text-white" /> : <CircularProgress className="!w-5 !h-5 text-white" />}
                                {isLoading && <span className="ml-1 text-white">Saving...</span>}
                                {!isLoading && <span className="ml-1 text-white">Save image</span>}
                            </div>
                        )}
                    </div>
                    <input ref={bannerImageInputRef} type="file" accept="image/*" className="hidden" onChange={onuploadFileChange} />
                </div>
            )}
        </div>
    );
}
