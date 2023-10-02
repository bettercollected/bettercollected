import React, { useRef, useState } from 'react';

import { useTranslation } from 'next-i18next';

import cn from 'classnames';
import html2canvas from 'html2canvas';
import { toast } from 'react-toastify';
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch';

import uploadImage from '@app/assets/images/upload.png';
import Image from '@app/components/ui/image';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import editWorkspace from '@app/constants/locales/edit-workpsace';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { BannerImageComponentPropType } from '@app/containers/dashboard/WorkspaceHomeContainer';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';
import AppButton from "@Components/Common/Input/Button/AppButton";

export default function BannerImageComponent(props: BannerImageComponentPropType) {
    const { workspace, isFormCreator } = props;
    const transformComponentRef = useRef(null);
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const [image, setImage] = useState('');
    const imageInputRef = useRef<HTMLInputElement>(null);
    const { t } = useTranslation();

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

    const onClickCancelButton = () => {
        setImage('');
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
                    toast(response.error.data || t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST });
                }
                if (response.data) {
                    toast(t(toastMessage.workspaceUpdate).toString(), { type: 'success', toastId: ToastId.SUCCESS_TOAST });
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
        <div className={cn('relative w-full bannerdiv aspect-banner-mobile lg:aspect-banner-desktop')}>
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
                                <img style={{ width: '100%', height: '100%', objectFit: 'cover' }} src={image} alt="test" />
                            </TransformComponent>
                        );
                    }}
                </TransformWrapper>
            ) : (
                <>
                    {!!workspace.bannerImage ? (
                        <Image src={workspace?.bannerImage ?? ''} priority layout="fill" objectFit="cover" objectPosition="center" alt={workspace?.title} />
                    ) : isFormCreator ? (
                        <div className="flex body1 text-black-700 flex-col gap-3 items-center justify-center h-full">
                            <Image src={uploadImage} height="29px" width="45px" alt={'upload'} />
                            <div className="cursor-pointer body6 !leading-none !text-brand-500" onClick={onClickFileUploadButton}>
                                {t(editWorkspace.uploadBannerImage)}
                            </div>
                            <div className="hidden md:flex body5 !leading-none !text-black-700">{t(editWorkspace.bannerAspectRatio)}</div>
                        </div>
                    ) : (
                        <div className="flex h-full justify-center items-center">{t(localesCommon.noImage)}</div>
                    )}
                    <input ref={imageInputRef} data-testid="file-upload" type="file" accept="image/*" className="hidden" onChange={onUploadFileChange} />
                </>
            )}
            {isFormCreator && (
                <UpdateImageOptions
                    t={t}
                    getUpdateOptionsClassName={getUpdateOptionsClassName}
                    isLoading={isLoading}
                    onClickFileUploadButton={onClickFileUploadButton}
                    onClickFileSaveButton={onClickFileSaveButton}
                    image={image}
                    onCLickCancelButton={onClickCancelButton}
                />
            )}
        </div>
    );
}

function UpdateImageOptions({ getUpdateOptionsClassName, isLoading, onClickFileUploadButton, onClickFileSaveButton, image, onCLickCancelButton, t }: any) {
    return (
        <div className={`absolute bottom-2 right-2 hidden ${getUpdateOptionsClassName()}`}>
            <div className="flex justify-between">
                {!isLoading && !image && <AppButton onClick={onClickFileUploadButton}>{t(buttonConstant.update)}</AppButton>}
                {!isLoading && image && (
                    <AppButton className="!text-white flex !bg-black-600 hover:!bg-black-700 mr-2"  onClick={onCLickCancelButton}>
                        {t(buttonConstant.cancel)}
                    </AppButton>
                )}
                {!!image && (
                    <>
                        <AppButton isLoading={isLoading} onClick={onClickFileSaveButton}>
                            {isLoading ? t(buttonConstant.saving) : t(buttonConstant.save)}
                        </AppButton>
                    </>
                )}
            </div>
        </div>
    );
}
