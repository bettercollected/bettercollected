import React, { useRef, useState } from 'react';

import { useTranslation } from 'next-i18next';

import AvatarEditor from 'react-avatar-editor';
import { toast } from 'react-toastify';

import Image from '@app/components/ui/image';
import { localesGlobal } from '@app/constants/locales/global';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { BannerImageComponentPropType } from '@app/containers/dashboard/WorkspaceHomeContainer';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

import AuthAccountProfileImage from '../auth/account-profile-image';
import { useModal } from '../modal-views/context';
import { useUpgradeModal } from '../modal-views/upgrade-modal-context';
import WorkSpaceLogoUi from '../ui/workspace-logo-ui';

export default function ProfileImageComponent(props: BannerImageComponentPropType) {
    const { workspace, isFormCreator } = props;
    const { t } = useTranslation();
    const [uploadImage, setUploadImage] = useState(workspace.profileImage);
    const profileInputRef = useRef<HTMLInputElement>(null);
    const profileEditorRef = useRef<AvatarEditor>(null);
    const { openModal, closeModal } = useUpgradeModal();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const dispatch = useAppDispatch();

    const onUploadFileChange = (e: any) => {
        if (e.target.files.length === 0) return;
        const image = e.target.files[0];
        openModal('CROP_IMAGE', { profileEditorRef: profileEditorRef, uploadImage: image, profileInputRef: profileInputRef, onSave: updateProfileHandler, modalIndex: 2, closeModal });
    };

    const updateProfileHandler = async () => {
        if (!!profileEditorRef.current) {
            const dataUrl = profileEditorRef.current.getImage().toDataURL();

            const result = await fetch(dataUrl);
            const blob = await result.blob();
            const file = new File([blob], 'profileImage.png', { type: blob.type });
            const formData = new FormData();
            formData.append('profile_image', file);

            const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
            if (response.error) {
                toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST });
            }
            if (response.data) {
                toast(t(toastMessage.workspaceUpdate).toString(), { type: 'success', toastId: ToastId.SUCCESS_TOAST });

                dispatch(setWorkspace(response.data));
                setUploadImage(response.data.profileImage);
                // await router.push(router.asPath, undefined);
            }
            closeModal();
        } else return;
    };

    return (
        <div className={props?.className ?? ''}>
            {isFormCreator ? (
                <>
                    <div onClick={() => profileInputRef.current?.click()} className="w-min cursor-pointer">
                        <AuthAccountProfileImage image={uploadImage} name={workspace.title} size={143} typography="h1" />
                        <input data-testid="file-upload-profile" type="file" accept="image/*" ref={profileInputRef} className="hidden" onChange={onUploadFileChange} />
                    </div>
                </>
            ) : (
                <div className={`relative bannerdiv aspect-square product-image bg-white ${!!workspace?.profileImage ? '' : 'border-[4px] border-brand-100 hover:border-brand-400'} z-10  w-24  sm:w-32  md:w-40  lg:w-[200px] overflow-hidden`}>
                    {!isFormCreator &&
                        (!!workspace.profileImage ? (
                            <Image src={workspace?.profileImage ?? ''} layout="fill" objectFit="contain" alt={workspace.title} />
                        ) : (
                            <div className="flex h-full justify-center text-center items-center">
                                {isFormCreator ? (
                                    <>
                                        <Image src="/upload.png" height="46px" width={'72px'} alt={'upload'} />
                                    </>
                                ) : (
                                    t(localesGlobal.noImage)
                                )}
                            </div>
                        ))}
                </div>
            )}
        </div>
    );
}
