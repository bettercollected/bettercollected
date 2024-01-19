import React, {FormEvent, useState} from 'react';

import {useTranslation} from 'next-i18next';
import {useRouter} from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import {ButtonSize} from '@Components/Common/Input/Button/AppButtonProps';
import UploadLogo from '@Components/Common/UploadLogo';
import {toast} from 'react-toastify';

import AuthNavbar from '@app/components/auth/navbar';
import TextFieldHandler from '@app/components/onboarding/TextFieldHandler';
import {onBoarding} from '@app/constants/locales/onboarding-screen';
import {toastMessage} from '@app/constants/locales/toast-message';
import {ToastId} from '@app/constants/toastId';
import {UserStatus} from '@app/models/dtos/UserStatus';
import {WorkspaceDto} from '@app/models/dtos/workspaceDto';
import {selectAuth} from '@app/store/auth/slice';
import {useAppDispatch, useAppSelector} from '@app/store/hooks';
import {useCreateWorkspaceMutation, usePatchExistingWorkspaceMutation} from '@app/store/workspaces/api';
import {setWorkspace} from '@app/store/workspaces/slice';

interface onBoardingProps {
    workspace?: WorkspaceDto;
    createWorkspace?: boolean;
}

export interface FormDataDto {
    title: string;
    description: string;
    workspaceLogo: any;
    workspaceName: string;
}

const OnboardingContainer = ({workspace, createWorkspace}: onBoardingProps) => {
    const {t} = useTranslation();
    const dispatch = useAppDispatch();
    const router = useRouter();
    const authStatus = useAppSelector(selectAuth);
    const user: UserStatus = !!authStatus ? authStatus : null;

    const [createWorkspaceRequest, data] = useCreateWorkspaceMutation();
    const [patchExistingWorkspace, {isLoading, isSuccess}] = usePatchExistingWorkspaceMutation();

    const workspaceName: string = (workspace?.workspaceName as string) === (workspace?.ownerId as string) ? '' : (workspace?.workspaceName as string);

    const [formData, setFormData] = useState<FormDataDto>({
        title: createWorkspace ? '' : (user?.firstName || user?.lastName || user?.email?.split('@')[0]) + "'s Workspace",
        description: workspace?.description ?? '',
        workspaceLogo: workspace?.profileImage ?? null,
        workspaceName: createWorkspace ? '' : workspaceName
    });

    const handleUploadLogo = (logo: File) => {
        setFormData({
            ...formData,
            workspaceLogo: logo
        });
    };

    const handleRemoveLogo = () => {
        setFormData({
            ...formData,
            workspaceLogo: ''
        });
    };

    const createNewWorkspace = async (skip: boolean) => {
        const createFormData = new FormData();
        if (formData.workspaceLogo && !skip) {
            createFormData.append('profile_image', formData.workspaceLogo);
        }
        createFormData.append('title', formData.title);
        createFormData.append('description', formData.description);
        createFormData.append('workspace_name', formData.workspaceName as string);
        const response: any = await createWorkspaceRequest(createFormData);
        if (response.error) {
            toast(response.error?.data || t(toastMessage.somethingWentWrong), {
                toastId: ToastId.ERROR_TOAST,
                type: 'error'
            });
        }
        if (response.data) {
            toast(t(toastMessage.workspaceUpdate).toString(), {type: 'success', toastId: ToastId.SUCCESS_TOAST});
            dispatch(setWorkspace(response.data));
            router.replace(`/${response.data?.workspaceName}/dashboard/forms`);
        }
    };

    const updateWorkspaceDetails = async (skip: boolean) => {
        const updateFormData = new FormData();
        if (formData.workspaceLogo && workspace?.profileImage !== formData.workspaceLogo && !skip) {
            updateFormData.append('profile_image', formData.workspaceLogo);
        }
        updateFormData.append('title', formData.title);
        updateFormData.append('description', formData.description);
        updateFormData.append('workspace_name', formData.workspaceName as string);
        const response: any = await patchExistingWorkspace({workspace_id: workspace?.id, body: updateFormData});
        if (response.error) {
            toast(response.error?.data || t(toastMessage.somethingWentWrong), {
                toastId: ToastId.ERROR_TOAST,
                type: 'error'
            });
        }
        if (response.data) {
            toast(t(toastMessage.workspaceUpdate).toString(), {type: 'success', toastId: ToastId.SUCCESS_TOAST});
            dispatch(setWorkspace(response.data));
            router.replace(`/${response.data?.workspaceName}/dashboard/forms`);
        }
    };

    const onClickDone = async (skip: boolean = false) => {
        if (createWorkspace) {
            await createNewWorkspace(skip);
        } else {
            await updateWorkspaceDetails(skip);
        }
    };

    const handleOnchange = (e: any) => {
        setFormData({
            ...formData,
            [e.target.id]: e.target.value
        });
    };


    const onSubmitForm = async (event: FormEvent) => {
        event.preventDefault();
        if (formData.title && formData.workspaceName) {
            await onClickDone();
        }
    };

    return (
        <div className="bg-white w-full flex flex-col items-center px-4 md:px-0">
            <AuthNavbar showPlans={false} showHamburgerIcon/>
            <div className="flex flex-col relative mt-32">
                <div className="h3-new">{t(onBoarding.addYourOrganization)}</div>
                <UploadLogo logoImageUrl={workspace?.profileImage ?? ''} className="mt-12" onUpload={handleUploadLogo}
                            onRemove={handleRemoveLogo}/>
                <form className="mt-12 md:w-[541px] space-y-8 " onSubmit={onSubmitForm}>
                    <AppTextField required title="Organization Name" id="title"
                                  placeholder="Enter name of your workspace" value={formData.title}
                                  onChange={handleOnchange}/>
                    <TextFieldHandler formData={formData} setFormData={setFormData} handleOnChange={handleOnchange}
                                      createWorkspace={createWorkspace}/>
                    <AppTextField title="Add Your Organization Description" id="description"
                                  placeholder="Write Description" multiline value={formData.description}
                                  onChange={handleOnchange}/>
                    <AppButton size={ButtonSize.Medium} className="w-full " type="submit"
                               disabled={!formData.title || !formData.workspaceName}>
                        {t(onBoarding.addNowButton)}
                    </AppButton>
                </form>
            </div>
        </div>
    );
};

export default OnboardingContainer;
