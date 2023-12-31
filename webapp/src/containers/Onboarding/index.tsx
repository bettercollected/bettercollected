import React, {FormEvent, useEffect, useState} from 'react';

import {useTranslation} from 'next-i18next';
import {useRouter} from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import UploadLogo from '@Components/Common/UploadLogo';
import {toast} from 'react-toastify';

import AuthNavbar from '@app/components/auth/navbar';
import {InfoIcon} from '@app/components/icons/info-icon';
import TextFieldHandler from '@app/components/onboarding/TextFieldHandler';
import {onBoarding} from '@app/constants/locales/onboarding-screen';
import {toastMessage} from '@app/constants/locales/toast-message';
import {ToastId} from '@app/constants/toastId';
import {UserStatus} from '@app/models/dtos/UserStatus';
import {WorkspaceDto} from '@app/models/dtos/workspaceDto';
import {selectAuth} from '@app/store/auth/slice';
import {useAppDispatch, useAppSelector} from '@app/store/hooks';
import {
    useCreateWorkspaceMutation,
    useLazyGetWorkspaceNameSuggestionsQuery,
    usePatchExistingWorkspaceMutation
} from '@app/store/workspaces/api';
import {setWorkspace} from '@app/store/workspaces/slice';
import {ButtonSize} from "@Components/Common/Input/Button/AppButtonProps";

interface onBoardingProps {
    workspace?: WorkspaceDto;
    createWorkspace?: boolean;
}

export interface FormDataDto {
    title: string;
    description: string;
    workspaceLogo: any;
    workspaceName: string | null;
}

const OnboardingContainer = ({workspace, createWorkspace}: onBoardingProps) => {
    const {t} = useTranslation();
    const dispatch = useAppDispatch();
    const router = useRouter();
    const authStatus = useAppSelector(selectAuth);
    const user: UserStatus = !!authStatus ? authStatus : null;

    const [createWorkspaceRequest, data] = useCreateWorkspaceMutation();
    const [patchExistingWorkspace, {isLoading, isSuccess}] = usePatchExistingWorkspaceMutation();
    const [trigger] = useLazyGetWorkspaceNameSuggestionsQuery();

    const workspaceName: string | null = (workspace?.workspaceName as string) === (workspace?.ownerId as string) ? null : (workspace?.workspaceName as string);

    const [formData, setFormData] = useState<FormDataDto>({
        title: (user?.firstName || user?.lastName || user?.email?.split('@')[0]) + "'s Workspace",
        description: workspace?.description ?? '',
        workspaceLogo: workspace?.profileImage ?? null,
        workspaceName: workspaceName
    });
    const [errorTitle, setErrorTitle] = useState(false);
    const [workspaceNameSuggestion, setWorkspaceNameSuggestion] = useState<string>('');
    const [errorWorkspaceName, setErrorWorkspaceName] = useState(false);
    const [isErrorOnWorkspaceNameField, setIsErrorOnWorkspaceNameField] = useState(false);

    useEffect(() => {
        if (formData.title) setErrorTitle(false);
        if (formData.workspaceName) setErrorWorkspaceName(false);
    }, [formData.title, formData.workspaceName]);


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
            router.replace(`/${response.data?.workspaceName}/dashboard`);
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
            router.replace(`/${response.data?.workspaceName}/dashboard`);
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

    const fetchSuggestionsForWorkspaceHandle = async (e: any) => {
        if (!!e.target.value) {
            const request = {
                workspaceId: workspace?.id,
                title: e.target.value.toLowerCase()
            };
            const {isSuccess, data} = await trigger(request);
            if (isSuccess) {
                const suggestion = data[Math.floor(Math.random() * 4) + 1];
                setWorkspaceNameSuggestion(suggestion);
                return;
            }
        }
        setWorkspaceNameSuggestion('');
        return;
    };

    const onSubmitForm = async (event: FormEvent) => {
        event.preventDefault();
        if (formData.title && formData.workspaceName) {
            await onClickDone();
        }
        if (!formData.title) setErrorTitle(true);

        if (!formData.workspaceName) setErrorWorkspaceName(true);
        return;
    };

    return (
        <div className="bg-white w-full flex flex-col items-center px-4 md:px-0">
            <AuthNavbar showPlans={false} showHamburgerIcon/>
            <div className="flex flex-col relative mt-32">
                <div className="h3-new">{t(onBoarding.addYourOrganization)}</div>
                <UploadLogo logoImageUrl={workspace?.profileImage ?? ''} className="mt-12" onUpload={handleUploadLogo}
                            onRemove={handleRemoveLogo}/>
                <form className="mt-12 md:w-[541px] space-y-8 " onSubmit={onSubmitForm}>
                    <div>
                        <AppTextField title="Organization Name" id="title" placeholder="Enter name of your workspace"
                                      value={formData.title} onChange={handleOnchange}
                                      onBlur={fetchSuggestionsForWorkspaceHandle} isError={errorTitle}/>
                        {errorTitle ? (
                            <div className={'text-red-600 text-xs md:text-sm !mt-2 flex items-center gap-2'}>
                                <InfoIcon className="w-4 h-4"/> <span>{t(onBoarding.fillOrganizationName)}</span>
                            </div>
                        ) : (
                            <></>
                        )}
                    </div>
                    <TextFieldHandler formData={formData}
                                      setFormData={setFormData} errorWorkspaceName={errorWorkspaceName}
                                      setIsErrorOnTextField={setIsErrorOnWorkspaceNameField}/>
                    < AppTextField title="Add Your Organization Description" id="description"
                                   placeholder="Write Description" multiline value={formData.description}
                                   onChange={handleOnchange}/>
                    <AppButton size={ButtonSize.Medium} className="w-full " type="submit"
                               disabled={isErrorOnWorkspaceNameField}>
                        {t(onBoarding.addNowButton)}
                    </AppButton>
                </form>
            </div>
        </div>
    );
};

export default OnboardingContainer;
