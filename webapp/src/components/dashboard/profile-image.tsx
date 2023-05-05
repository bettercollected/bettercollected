import React, { useRef } from 'react';
import { useState } from 'react';

import { useRouter } from 'next/router';

import _ from 'lodash';

import ModeEditIcon from '@mui/icons-material/ModeEdit';
import { Dialog } from '@mui/material';
import AvatarEditor from 'react-avatar-editor';
import { toast } from 'react-toastify';

import Button from '@app/components/ui/button';
import Image from '@app/components/ui/image';
import { ToastId } from '@app/constants/toastId';
import { BannerImageComponentPropType } from '@app/containers/dashboard/WorkspaceHomeContainer';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

import { useModal } from '../modal-views/context';
import WorkSpaceLogoUi from '../ui/workspace-logo-ui';

export default function ProfileImageComponent(props: BannerImageComponentPropType) {
    const { workspace, isFormCreator } = props;
    const [uploadImage, setUploadImage] = useState(workspace.profileImage);
    const profileInputRef = useRef<HTMLInputElement>(null);
    const profileEditorRef = useRef<AvatarEditor>(null);
    const { openModal, closeModal } = useModal();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const dispatch = useAppDispatch();

    const onUploadFileChange = (e: any) => {
        if (e.target.files.length === 0) return;
        const image = e.target.files[0];
        openModal('CROP_IMAGE', { profileEditorRef: profileEditorRef, uploadImage: image, isLoading: isLoading, profileInputRef: profileInputRef, onSave: updateProfileHandler });
    };

    // const onEditButtonClick = () => {
    //     if (!workspace.profileImage) return;
    //     setUploadImage(workspace.profileImage);
    //     openModal('CROP_IMAGE', { profileEditorRef: profileEditorRef, uploadImage: uploadImage, isLoading: isLoading, profileInputRef: profileInputRef, onSave: updateProfileHandler });
    // };

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
                toast('Something went wrong', { toastId: ToastId.ERROR_TOAST });
            }
            if (response.data) {
                toast('Workspace Updated', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
                // @ts-ignore

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
                    <WorkSpaceLogoUi workspaceLogoRef={profileInputRef} onChange={onUploadFileChange} onClick={() => profileInputRef.current?.click()} image={uploadImage} profileName={workspace.title}></WorkSpaceLogoUi>
                    {/* <input data-testid="file-upload-profile" ref={profileInputRef} type="file" accept="image/*" className="hidden" onChange={onUploadFileChange} /> */}
                </>
            ) : (
                <div className={`relative bannerdiv aspect-square product-image bg-white ${!!workspace?.profileImage ? '' : 'border-[4px] border-brand-100 hover:border-brand-400'} z-10  w-24  sm:w-32  md:w-40  lg:w-[200px] overflow-hidden`}>
                    {!isFormCreator &&
                        (!!workspace.profileImage ? (
                            <Image src={workspace?.profileImage ?? ''} layout="fill" objectFit="contain" alt={workspace.title} />
                        ) : (
                            <div className="flex h-full justify-center items-center">
                                {isFormCreator ? (
                                    <>
                                        <Image src="/upload.png" height="46px" width={'72px'} alt={'upload'} />
                                    </>
                                ) : (
                                    'No image available'
                                )}
                            </div>
                        ))}
                </div>
            )}
        </div>
    );
}
