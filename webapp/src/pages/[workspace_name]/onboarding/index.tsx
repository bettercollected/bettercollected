import React, { FormEvent, useEffect, useRef, useState } from 'react';

import { GetServerSidePropsContext } from 'next';
import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import UploadLogo from '@Components/Common/UploadLogo';
import { ChevronLeft } from '@mui/icons-material';
import cn from 'classnames';
import AvatarEditor from 'react-avatar-editor';
import { toast } from 'react-toastify';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import AuthNavbar from '@app/components/auth/navbar';
import { InfoIcon } from '@app/components/icons/info-icon';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Logo from '@app/components/ui/logo';
import WorkSpaceLogoUi from '@app/components/ui/workspace-logo-ui';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { onBoarding } from '@app/constants/locales/onboarding-screen';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { validationMessage } from '@app/constants/locales/validation-message';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { ToastId } from '@app/constants/toastId';
import Layout from '@app/layouts/_layout';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { UserStatus } from '@app/models/dtos/UserStatus';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateWorkspaceMutation, useLazyGetWorkspaceNameAvailabilityQuery, useLazyGetWorkspaceNameSuggestionsQuery, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';
import { getFullNameFromUser } from '@app/utils/userUtils';

interface FormDataDto {
    title: string;
    description: string;
    workspaceLogo: any;
    workspaceName: string | null;
}

interface onBoardingProps {
    workspace?: WorkspaceDto;
    createWorkspace?: boolean;
}

export async function getServerSideProps(_context: GetServerSidePropsContext) {
    const authUserProps = (await getAuthUserPropsWithWorkspace(_context)).props;
    if (!authUserProps) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }
    if (authUserProps && authUserProps?.workspace?.title && authUserProps?.workspace?.title.toLowerCase() !== 'untitled') {
        return {
            redirect: {
                permanent: false,
                destination: `/${authUserProps.workspace.workspaceName}/dashboard`
            }
        };
    }
    return {
        props: { ...authUserProps }
    };
}

export default function Onboarding({ workspace, createWorkspace }: onBoardingProps) {
    const { t } = useTranslation();
    const router = useRouter();
    const authStatus = useAppSelector(selectAuth);
    const { openModal, closeModal } = useModal();
    const user: UserStatus = !!authStatus ? authStatus : null;
    let workspaceLogoRef = useRef<HTMLInputElement>(null);
    const profileEditorRef = useRef<AvatarEditor>(null);
    const dispatch = useAppDispatch();
    const [isError, setError] = useState(false);
    const [workspaceNameSuggestion, setWorkspaceNameSuggestion] = useState<string>('');
    const [isWorkspaceNameAvailable, setIsWorkspaceNameAvailable] = useState<boolean | null>(null);
    const profileName = getFullNameFromUser(user);
    const [stepCount, setStepCount] = useState(createWorkspace ? 1 : 0);
    const [patchExistingWorkspace, { isLoading, isSuccess }] = usePatchExistingWorkspaceMutation();
    const [trigger] = useLazyGetWorkspaceNameSuggestionsQuery();
    const [getWorkspaceAvailability, { isLoading: isCheckingHandleName }] = useLazyGetWorkspaceNameAvailabilityQuery();
    const [createWorkspaceRequest, data] = useCreateWorkspaceMutation();
    const workspaceName: string | null = (workspace?.workspaceName as string) === (workspace?.ownerId as string) ? null : (workspace?.workspaceName as string);
    const [formData, setFormData] = useState<FormDataDto>({
        title: workspace?.title.toLowerCase() !== 'untitled' ? workspace?.title || '' : '',
        description: workspace?.description ?? '',
        workspaceLogo: workspace?.profileImage ?? null,
        workspaceName: workspaceName
    });

    console.log(formData);
    useEffect(() => {
        if (formData.workspaceName === null) return;

        async function getAvailability() {
            return await getAvailabilityStatusOfWorkspaceName(formData.workspaceName as string);
        }

        getAvailability().then((res) => setIsWorkspaceNameAvailable(res));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [formData.workspaceName]);

    const increaseStep = () => {
        setStepCount(stepCount + 1);
    };
    const decreaseStep = () => {
        setStepCount(stepCount - 1);
    };

    const checkIfInvalidCharactersPresentInHandler = () => {
        if (!formData.workspaceName) return false;
        const validHandlePattern = /^[a-z0-9_]+$/;
        return !validHandlePattern.test(formData.workspaceName);
    };

    const handleFile = async (e: any) => {
        const image = e.target.files[0];
        const MB = 1048576;
        if (image.size / MB > 100) {
            toast(t(toastMessage.imageSizeRestriction).toString(), { toastId: ToastId.ERROR_TOAST });
        } else {
            openModal('CROP_IMAGE', {
                profileEditorRef: profileEditorRef,
                uploadImage: image,
                profileInputRef: workspaceLogoRef,
                onSave: handleUpdateProfile,
                modalIndex: 1,
                closeModal
            });
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
            const { isSuccess, data } = await trigger(e.target.value.toLowerCase());
            if (isSuccess) {
                const suggestion = data[Math.floor(Math.random() * 4) + 1];
                setWorkspaceNameSuggestion(suggestion);
                return;
            }
        }
        setWorkspaceNameSuggestion('');
        return;
    };

    const setWorkspaceSuggestionToWorkspaceNameField = (suggestion: string) => {
        setFormData({ ...formData, workspaceName: suggestion });
    };

    const getAvailabilityStatusOfWorkspaceName = async (workspaceName: string | null) => {
        if (!workspaceName) return false;
        if (checkIfInvalidCharactersPresentInHandler()) return false;
        const { isSuccess, data } = await getWorkspaceAvailability(workspaceName);
        if (isSuccess) {
            return data === 'True';
        }
        return false;
    };

    const handleUpdateProfile = async () => {
        if (!!profileEditorRef.current) {
            const dataUrl = profileEditorRef.current.getImage().toDataURL();
            const result = await fetch(dataUrl);
            const blob = await result.blob();
            const file = new File([blob], 'profileImage.png', { type: blob.type });
            setFormData({
                ...formData,
                workspaceLogo: file
            });
            closeModal();
        }
    };

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

    const onClickDone = async (skip: boolean = false) => {
        if (createWorkspace) {
            await createNewWorkspace(skip);
        } else {
            await updateWorkspaceDetails(skip);
        }
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
            toast(t(toastMessage.workspaceUpdate).toString(), { type: 'success', toastId: ToastId.SUCCESS_TOAST });
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
        const response: any = await patchExistingWorkspace({ workspace_id: workspace?.id, body: updateFormData });
        if (response.error) {
            toast(response.error?.data || t(toastMessage.somethingWentWrong), {
                toastId: ToastId.ERROR_TOAST,
                type: 'error'
            });
        }
        if (response.data) {
            toast(t(toastMessage.workspaceUpdate).toString(), { type: 'success', toastId: ToastId.SUCCESS_TOAST });
            dispatch(setWorkspace(response.data));
            router.replace(`/${response.data?.workspaceName}/dashboard`);
        }
    };

    const checkErrorTypeForHandleName = (string: string | null): any => {
        if (string == '') return 'Please fill the handle name';
        else if (string?.includes(' ')) return 'Spaces are not allowed in this field';
        else return 'Handle name already taken. Try another.';
    };

    const StepZeroContent = (
        <>
            <div className="flex flex-col gap-2 justify-center items-center mt-[60px]">
                <Logo isLink={false} />
                <p className="text-black-800 text-xs"> Privacy-friendly form builder</p>
            </div>
            <div className="flex flex-col mt-[120px] items-center w-full h-full">
                <AuthAccountProfileImage image={user?.profileImage} name={user?.firstName || user?.lastName || user?.email} size={100} typography="!text-6xl" />
                <p className="pt-10 text-center text-black-900 text-2xl font-semibold">
                    {t(localesCommon.hey)} {user?.firstName || user?.email}!
                </p>
                <p className="pt-3 text-black-800 text-base">{t(onBoarding.welcomeMessage)}</p>
                {/* <p className="mt-4 paragraph text-center text-black-700 md:w-[320px] w-full">{t(onBoarding.description)}</p> */}
                <AppButton className="mt-6 !py-3 px-8 bg-new-blue-500 hover:bg-brand-600" onClick={increaseStep}>
                    Add Your Organization
                </AppButton>
                {/* <p className="body2 !text-black-600 italic">{t(onBoarding.timeMessage)}</p> */}
            </div>
        </>
    );
    const AddWorkspaceHeader = (
        <div className="flex justify-between items-center">
            <div className=" cursor-pointer hover:bg-blue-200 rounded" onClick={decreaseStep}>
                {stepCount === 1 && createWorkspace ? <></> : <ChevronLeft className="h-6 w-6" />}
            </div>
            <p className="body4 text-black-700">
                {t(localesCommon.step)} {stepCount} {t(localesCommon.of)} 2
            </p>
        </div>
    );
    const StepOneContent = (
        <div className="bg-white w-full flex flex-col items-center px-4 md:px-0">
            <AuthNavbar showPlans={false} showHamburgerIcon />
            <div className="flex flex-col relative mt-32">
                <div className="h3-new">Add Your Organization</div>
                <UploadLogo logoImageUrl={workspace?.profileImage ?? ''} className="mt-12" onUpload={handleUploadLogo} onRemove={handleRemoveLogo} />
                <form
                    className="mt-12 md:w-[541px] space-y-8 "
                    onSubmit={async (event: FormEvent) => {
                        event.preventDefault();
                        await onClickDone();
                    }}
                >
                    <AppTextField required title="Organization Name" id="title" placeholder="Enter name of your workspace" value={formData.title} onChange={handleOnchange} onBlur={fetchSuggestionsForWorkspaceHandle} />
                    <div>
                        <AppTextField required title="Handle Name" id="workspaceName" placeholder="Enter workspace handle name" value={formData.workspaceName} onChange={handleOnchange} isError={!isWorkspaceNameAvailable}>
                            <AppTextField.Description>
                                Use smallcase for your handle name (eg: abc) <br />
                                https://bettercollected-admin.sireto.dev/<span className="text-pink-500">{formData.workspaceName}</span>/dashboard
                            </AppTextField.Description>
                        </AppTextField>
                        {isWorkspaceNameAvailable || isWorkspaceNameAvailable == null || isCheckingHandleName ? (
                            <></>
                        ) : (
                            <>
                                <div className={'text-red-600 text-xs md:text-sm !mt-2 flex items-center gap-1'}>
                                    <InfoIcon className="w-4 h-4" /> {checkErrorTypeForHandleName(formData.workspaceName)}
                                </div>
                                {workspaceNameSuggestion && (
                                    <div className={'flex items-center flex-wrap !mt-2'}>
                                        <p className={'text-sm'}>Available: &nbsp; </p>
                                        <p className={'text-sm font-semibold text-blue-500 cursor-pointer'} onClick={() => setWorkspaceSuggestionToWorkspaceNameField(workspaceNameSuggestion)}>
                                            {` ${workspaceNameSuggestion}`}
                                        </p>
                                    </div>
                                )}
                            </>
                        )}
                    </div>

                    <AppTextField title="Add Your Organization Description" id="description" placeholder="Write Description" multiline value={formData.description} onChange={handleOnchange} />
                    <AppButton className="!w-full bg-new-blue-500 !py-3 !px-8 !mt-12 hover:bg-brand-600" type="submit">
                        Add Now
                    </AppButton>
                </form>
            </div>
        </div>
    );

    if (isSuccess) return <FullScreenLoader />;
    return (
        <div className="flex flex-col w-full min-w-0 bg-white h-screen items-center overflow-auto pb-20">
            {stepCount === 0 && StepZeroContent}
            {stepCount === 1 && StepOneContent}
        </div>
    );
}
