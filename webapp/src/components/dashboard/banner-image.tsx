import React, { useRef } from 'react';
import { useState } from 'react';

import ModeEditIcon from '@mui/icons-material/ModeEdit';
import SaveIcon from '@mui/icons-material/Save';
import { CircularProgress } from '@mui/material';
import html2canvas from 'html2canvas';
import { toast } from 'react-toastify';
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch';

import Image from '@app/components/ui/image';
import { ToastId } from '@app/constants/toastId';
import { BannerImageComponentPropType } from '@app/containers/dashboard/WorkspaceHomeContainer';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function BannerImageComponent(props: BannerImageComponentPropType) {
    const { workspace, isFormCreator } = props;
    const transformComponentRef = useRef(null);

    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const [image, setImage] = useState('');
    const imageInputRef = useRef<HTMLInputElement>(null);

    const dispatch = useAppDispatch();
    const onUploadFileChange = (e: any) => {
        if (!e.target.files.length) return;
        setImage(URL.createObjectURL(e.target.files[0]));
    };

    const onClickFileUploadButton = () => {
        if (!!imageInputRef.current) {
            imageInputRef.current.click();
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
                    setImage('');
                    dispatch(setWorkspace(response.data));
                }
            });
        });
    };

    const getUpdateOptionsClassName = () => {
        if (!image && !workspace.bannerImage) {
            return '';
        }
        return '!block';
    };

    return (
        <div className="relative aspect-banner border rounded border-brand-300 w-full  bannerdiv">
            {!!image ? (
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
                                <img style={{ width: '100%', height: '100%' }} src={image} alt="test" />
                            </TransformComponent>
                        );
                    }}
                </TransformWrapper>
            ) : (
                <>
                    {!!workspace.bannerImage ? (
                        <Image src={workspace?.bannerImage ?? ''} priority layout="fill" objectFit="cover" objectPosition="center" alt={workspace?.title} />
                    ) : isFormCreator ? (
                        <div className="flex body1 text-black-700 flex-col  lg:space-y-5 items-center justify-center h-full">
                            <Image src="/upload.png" height="46px" width={'72px'} alt={'upload'} />
                            <div>
                                <span className=" cursor-pointer text-brand-500" onClick={onClickFileUploadButton}>
                                    Upload
                                </span>{' '}
                                a Image
                            </div>
                            <div className="hidden lg:flex">You can drag to adjust the image.</div>
                        </div>
                    ) : (
                        <div className="flex h-full justify-center items-center">No image available</div>
                    )}
                    <input ref={imageInputRef} data-testid="file-upload" type="file" accept="image/*" className="hidden" onChange={onUploadFileChange} />
                </>
            )}
            {isFormCreator && <UpdateImageOptions getUpdateOptionsClassName={getUpdateOptionsClassName} isLoading={isLoading} onClickFileUploadButton={onClickFileUploadButton} onClickFileSaveButton={onClickFileSaveButton} image={image} />}
        </div>
    );
}

function UpdateImageOptions({ getUpdateOptionsClassName, isLoading, onClickFileUploadButton, onClickFileSaveButton, image }: any) {
    return (
        <div className={`absolute bottom-2 right-2 hidden ${getUpdateOptionsClassName()}`}>
            <div className="flex justify-between">
                {!isLoading && (
                    <div className="p-2 ml-2 my-19 flex !bg-blue-600 hover:bg-blue-700 cursor-pointer rounded-md" onClick={onClickFileUploadButton}>
                        <ModeEditIcon className="!w-5 !h-5 text-white" />
                        <span className="ml-1 hidden lg:flex  text-white">Update Banner</span>
                    </div>
                )}
                {!!image && (
                    <div
                        data-testid="save-button"
                        style={{ pointerEvents: isLoading ? 'none' : 'auto' }}
                        className={`p-2 ml-2 ${isLoading ? 'bg-gray-500' : '!bg-blue-600'} my-19 flex justify-center items-center  hover:bg-blue-700 cursor-pointer rounded-md`}
                        onClick={onClickFileSaveButton}
                    >
                        {!isLoading ? <SaveIcon className="!w-5 !h-5 text-white" /> : <CircularProgress className="!w-5 !h-5 text-white" />}
                        {isLoading && <span className="ml-1 hidden lg:block text-white">Saving...</span>}
                        {!isLoading && <span className="ml-1 hidden lg:block text-white">Save image</span>}
                    </div>
                )}
            </div>
        </div>
    );
}
