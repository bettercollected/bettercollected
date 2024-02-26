import React, { useRef, useState } from 'react';

import { useTranslation } from 'next-i18next';

import AvatarEditor from 'react-avatar-editor';
import { toast } from 'react-toastify';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { BannerImageComponentPropType } from '@app/containers/dashboard/WorkspaceHomeContainer';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

import AuthAccountProfileImage from '../auth/account-profile-image';


export default function ProfileImageComponent(props: BannerImageComponentPropType) {
    const { workspace, isFormCreator, size } = props;
    const { t } = useTranslation();
    const [uploadImage, setUploadImage] = useState(workspace.profileImage);
    const profileInputRef = useRef<HTMLInputElement>(null);
    const profileEditorRef = useRef<AvatarEditor>(null);
    const { openModal, closeModal } = useFullScreenModal();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const dispatch = useAppDispatch();

    const onUploadFileChange = (e: any) => {
        if (e.target.files.length === 0) return;
        const image = e.target.files[0];
        openModal('CROP_IMAGE', {
            profileEditorRef: profileEditorRef,
            uploadImage: image,
            profileInputRef: profileInputRef,
            onSave: updateProfileHandler,
            modalIndex: 2,
            closeModal
        });
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
            <>
                <div
                    onClick={() => {
                        if (isFormCreator) {
                            profileInputRef.current?.click();
                        }
                    }}
                    className={`w-min ${isFormCreator ? 'cursor-pointer' : ''} `}
                >
                    <AuthAccountProfileImage image={uploadImage} name={workspace.title} size={size ? size : 163} typography="h2" />
                    <input data-testid="file-upload-profile" type="file" accept="image/*" ref={profileInputRef} className="hidden" onChange={onUploadFileChange} />
                </div>
            </>
        </div>
    );
}