import React, { useEffect, useRef, useState } from 'react';

import { GetServerSidePropsContext } from 'next';
import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { ChevronLeft } from '@mui/icons-material';
import cn from 'classnames';
import AvatarEditor from 'react-avatar-editor';
import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
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
    workspaceName: null | string;
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
    const [workspaceNameSuggestions, setWorkspaceNameSuggestions] = useState<Array<string>>([]);
    const [isWorkspaceNameAvailable, setIsWorkspaceNameAvailable] = useState<boolean | null>(null);
    const profileName = getFullNameFromUser(user);
    const [stepCount, setStepCount] = useState(createWorkspace ? 1 : 0);
    const [patchExistingWorkspace, { isLoading, isSuccess }] = usePatchExistingWorkspaceMutation();
    const [trigger] = useLazyGetWorkspaceNameSuggestionsQuery();
    const [getWorkspaceAvailability] = useLazyGetWorkspaceNameAvailabilityQuery();
    const [createWorkspaceRequest, data] = useCreateWorkspaceMutation();
    const workspaceName: string | null = (workspace?.workspaceName as string) === (workspace?.ownerId as string) ? null : (workspace?.workspaceName as string);
    const [formData, setFormData] = useState<FormDataDto>({
        title: workspace?.title.toLowerCase() !== 'untitled' ? workspace?.title || '' : '',
        workspaceName: workspaceName,
        description: workspace?.description ?? '',
        workspaceLogo: workspace?.profileImage ?? null
    });

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
                setWorkspaceNameSuggestions(data);
                return;
            }
        }
        setWorkspaceNameSuggestions([]);
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
            router.replace(`/${response?.data?.workspaceName}/dashboard`);
        }
    };

    const StepZeroContent = (
        <div className="flex flex-col mt-[24px] justify-center items-center">
            <AuthAccountProfileImage image={user?.profileImage} name={profileName} size={143} />
            <p className="pt-6 text-center text-black-900 h4">
                {t(localesCommon.hey)} {user?.firstName}! <br /> {t(onBoarding.welcomeMessage)}
            </p>
            <p className="mt-4 paragraph text-center text-black-700 md:w-[320px] w-full">{t(onBoarding.description)}</p>
            <Button size="large" className="mt-10 mb-4" onClick={increaseStep}>
                {t(buttonConstant.createWorkspace)}
            </Button>
            <p className="body2 !text-black-600 italic">{t(onBoarding.timeMessage)}</p>
        </div>
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
        <div className="md:w-[454px] w-full  p-10 bg-white rounded">
            {AddWorkspaceHeader}
            <div className="pl-2">
                <p className="mt-7 mb-8 h4 text-black-900">{t(onBoarding.addWorkspace)}</p>
                <p className=" mb-3 body1 text-black-900">
                    {t(workspaceConstant.title)}
                    <span className="text-red-500">*</span>
                </p>
                <BetterInput
                    InputProps={{
                        sx: {
                            height: '46px',
                            borderColor: '#0764EB !important'
                        }
                    }}
                    id="title"
                    error={formData.title === '' && isError}
                    placeholder={t(placeHolder.workspaceTitle)}
                    className="w-full !mb-0"
                    value={formData.title}
                    onChange={handleOnchange}
                    onBlur={fetchSuggestionsForWorkspaceHandle}
                />
                {formData.title === '' && isError && <p className="body4 !text-red-500 mt-2 h-[10px]">{t(validationMessage.workspaceTitle)}</p>}

                {/* workspace handle */}
                <p className=" mb-3 mt-6 body1 text-black-900">
                    {t(workspaceConstant.handle)}
                    <span className="text-red-500">*</span>
                </p>
                <BetterInput
                    InputProps={{
                        sx: {
                            height: '46px',
                            borderColor: '#0764EB !important'
                        },
                        endAdornment: (
                            <div className={'min-w-fit italic'}>
                                {isWorkspaceNameAvailable === null || formData.workspaceName === workspace?.workspaceName ? (
                                    <></>
                                ) : isWorkspaceNameAvailable ? (
                                    <p className={'text-green-600 text-xs md:text-sm'}>&#10004; {t(onBoarding.workspaceNameAvailable)}</p>
                                ) : (
                                    <p className={'text-red-600 text-xs md:text-sm'}>&#10007; {t(onBoarding.workspaceNameNotAvailable)}</p>
                                )}
                            </div>
                        )
                    }}
                    id="workspaceName"
                    error={formData.workspaceName === '' && isError}
                    placeholder={t(placeHolder.enterWorkspaceHandle)}
                    className="w-full !mb-0"
                    value={!formData.workspaceName ? '' : formData.workspaceName}
                    onChange={handleOnchange}
                />
                {formData.workspaceName === '' && isError && <p className="body4 !text-red-500 !mb-4 h-[10px]">{t(validationMessage.workspaceName)}</p>}
                {isError && checkIfInvalidCharactersPresentInHandler() && <p className="body4 !text-red-500 !mb-4 !text-xs h-[10px]">{t(validationMessage.workspaceNameInvalidCharacter)}</p>}

                <div className={'flex italic items-center flex-wrap'}>
                    {workspaceNameSuggestions.length ? <p className={'text-sm'}>{t(onBoarding.suggestions)}&nbsp;</p> : <></>}
                    {workspaceNameSuggestions
                        .filter((w) => w !== formData.workspaceName)
                        .map((suggestion, idx) => (
                            <p key={suggestion} className={'text-sm text-blue-500 cursor-pointer'} onClick={() => setWorkspaceSuggestionToWorkspaceNameField(suggestion)}>
                                {suggestion}
                                {idx === workspaceNameSuggestions.filter((w) => w !== formData.workspaceName).length - 1 ? <></> : <span>,&nbsp;</span>}
                            </p>
                        ))}
                </div>

                {/* workspace description */}

                <p className={cn('mb-3 body1 text-black-900', formData.title === '' && isError ? 'mt-[24px]' : 'mt-[42px]')}>{t(localesCommon.description)}</p>
                <BetterInput
                    inputProps={{ maxLength: 280 }}
                    className="!border-solid !border-gray-300 !text-gray-900 !body3 !rounded !w-full"
                    size="medium"
                    rows={4}
                    multiline
                    onChange={handleOnchange}
                    value={formData.description}
                    id="description"
                    name="description"
                    placeholder={t(placeHolder.description)}
                />
            </div>
            <div className="flex justify-end mt-8">
                <Button
                    size="medium"
                    onClick={async () => {
                        if (formData.title !== '' && formData.workspaceName !== '' && !checkIfInvalidCharactersPresentInHandler() && (await getAvailabilityStatusOfWorkspaceName(formData.workspaceName))) {
                            increaseStep();
                        } else {
                            setError(true);
                        }
                    }}
                >
                    {t(buttonConstant.next)}
                </Button>
            </div>
        </div>
    );
    const StepTwoContent = (
        <div className="md:w-[454px] w-full  p-10 bg-white rounded">
            {AddWorkspaceHeader}
            <p className="mt-7 mb-8  h4 text-brand-900">{t(onBoarding.addWorkspaceLogo)}</p>
            {/* <div className="flex md:flex-row flex-col gap-4 items-center">
                <AuthAccountProfileImage image={formProvider.workspaceLogo && URL.createObjectURL(formProvider.workspaceLogo)} name={profileName} size={143} typography="h1" /> */}
            <WorkSpaceLogoUi
                workspaceLogoRef={workspaceLogoRef}
                onChange={handleFile}
                onClick={() => workspaceLogoRef.current?.click()}
                image={formData.workspaceLogo && (formData.workspaceLogo.toString().startsWith('https') ? formData.workspaceLogo : URL.createObjectURL(formData.workspaceLogo))}
                profileName={profileName}
            ></WorkSpaceLogoUi>
            {/* </div> */}
            <div className="flex justify-between mt-8 items-center">
                <div
                    className="text-brand-500 hover:underline hover:cursor-pointer"
                    onClick={async () => {
                        await onClickDone(true);
                    }}
                >
                    {t(buttonConstant.skip)}
                </div>

                <Button
                    size="medium"
                    onClick={async () => {
                        await onClickDone();
                    }}
                    isLoading={isLoading || data?.isLoading}
                >
                    {t(buttonConstant.done)}
                </Button>
            </div>
        </div>
    );

    if (isSuccess) return <FullScreenLoader />;
    return (
        <Layout showNavbar showAuthAccount={!!createWorkspace} isCustomDomain>
            <div className=" flex flex-col my-[40px] items-center">
                {stepCount === 0 && StepZeroContent}
                {stepCount === 1 && StepOneContent}
                {stepCount === 2 && StepTwoContent}
            </div>
        </Layout>
    );
}
