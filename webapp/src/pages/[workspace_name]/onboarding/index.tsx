import React, { useRef, useState } from 'react';

import { GetServerSidePropsContext } from 'next';
import { useRouter } from 'next/router';

import _ from 'lodash';

import { ChevronLeft } from '@mui/icons-material';
import { TextField } from '@mui/material';
import cn from 'classnames';
import AvatarEditor from 'react-avatar-editor';
import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import WorkSpaceLogoUi from '@app/components/ui/workspace-logo-ui';
import { ToastId } from '@app/constants/toastId';
import Layout from '@app/layouts/_layout';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateWorkspaceMutation, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

interface FormDataDto {
    title: string;
    description: string;
    workspaceLogo: any;
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
    if (authUserProps && authUserProps.workspace.title.toLowerCase() !== 'untitled') {
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
    const router = useRouter();
    const authStatus = useAppSelector(selectAuth);
    const { openModal, closeModal } = useModal();
    const user: any = !!authStatus ? authStatus : null;
    let workspaceLogoRef = useRef<HTMLInputElement>(null);
    const profileEditorRef = useRef<AvatarEditor>(null);
    const dispatch = useAppDispatch();
    const [isError, setError] = useState(false);
    const profileName = _.capitalize(user?.first_name) + ' ' + _.capitalize(user?.last_name);
    const [stepCount, setStepCount] = useState(createWorkspace ? 1 : 0);
    const [patchExistingWorkspace, { isLoading, isSuccess }] = usePatchExistingWorkspaceMutation();
    const [createWorkspaceRequest, data] = useCreateWorkspaceMutation();
    const [formData, setFormData] = useState<FormDataDto>({
        title: workspace?.title.toLowerCase() !== 'untitled' ? workspace?.title || '' : '',
        description: workspace?.description ?? '',
        workspaceLogo: workspace?.profileImage ?? ''
    });
    const increaseStep = () => {
        setStepCount(stepCount + 1);
    };
    const decreaseStep = () => {
        setStepCount(stepCount - 1);
    };
    const handleFile = async (e: any) => {
        const image = e.target.files[0];
        const MB = 1048576;
        if (image.size / MB > 100) {
            toast('Image size is greater than 100MB', { toastId: ToastId.ERROR_TOAST });
        } else {
            openModal('CROP_IMAGE', {
                profileEditorRef: profileEditorRef,
                uploadImage: image,
                profileInputRef: workspaceLogoRef,
                onSave: handleUpdateProfile
            });
        }
    };
    const handleOnchange = (e: any) => {
        setFormData({
            ...formData,
            [e.target.id]: e.target.value
        });
    };

    const handleUpdateProfile = async (e: any) => {
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

    const onClickDone = async () => {
        if (createWorkspace) {
            await createNewWorkspace();
        } else {
            await updateWorkspaceDetails();
        }
    };

    const createNewWorkspace = async () => {
        const createFormData = new FormData();
        if (formData.workspaceLogo) {
            createFormData.append('profile_image', formData.workspaceLogo);
        }
        createFormData.append('title', formData.title);
        createFormData.append('description', formData.description);
        const response: any = await createWorkspaceRequest(createFormData);
        if (response.error) {
            toast(response.error?.data || 'Something went wrong', { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
        if (response.data) {
            toast('Workspace Updated', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
            dispatch(setWorkspace(response.data));
            router.replace(`/${response.data?.workspaceName}/dashboard`);
        }
    };

    const updateWorkspaceDetails = async () => {
        const updateFormData = new FormData();
        if (formData.workspaceLogo && workspace?.profileImage !== formData.workspaceLogo) {
            updateFormData.append('profile_image', formData.workspaceLogo);
        }
        updateFormData.append('title', formData.title);
        updateFormData.append('description', formData.description);
        const response: any = await patchExistingWorkspace({ workspace_id: workspace?.id, body: updateFormData });
        if (response.error) {
            toast(response.error?.data || 'Something went wrong', { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
        if (response.data) {
            toast('Workspace Updated', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
            dispatch(setWorkspace(response.data));
            router.replace(`/${workspace?.workspaceName}/dashboard`);
        }
    };

    const StepZeroContent = (
        <div className="flex flex-col mt-[24px] justify-center items-center">
            <AuthAccountProfileImage image={user?.profile_image} name={profileName} size={143} />
            <p className="pt-6 text-center text-black-900 h4">
                Hey {user?.first_name}! <br /> Welcome to BetterCollected{' '}
            </p>
            <p className="mt-4 paragraph text-center text-black-700 md:w-[320px] w-full">Please create your workspace so that your team know you are here.</p>
            <Button size="large" className="mt-10 mb-4" onClick={increaseStep}>
                {workspace?.profileImage || workspace?.description || workspace?.title.toLowerCase() !== 'untitled' ? 'Update A Workspace' : 'Create A Workspace'}
            </Button>
            <p className="body2 !text-black-600 italic">It will only take few minutes</p>
        </div>
    );
    const AddWorkspaceHeader = (
        <div className="flex justify-between items-center">
            <div className=" cursor-pointer hover:bg-blue-200 rounded" onClick={decreaseStep}>
                {stepCount === 1 && createWorkspace ? <></> : <ChevronLeft className="h-6 w-6" />}
            </div>
            <p className="body4 text-black-700">Step {stepCount} of 2</p>
        </div>
    );
    const StepOneContent = (
        <div className="md:w-[454px] w-full  p-10 bg-white rounded">
            {AddWorkspaceHeader}
            <div className="pl-2">
                <p className="mt-7 mb-8 h4 text-black-900">Add your workspace</p>
                <p className=" mb-3 body1 text-black-900">
                    Workspace title<span className="text-red-500">*</span>
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
                    placeholder="Eg. Sireto Technology"
                    className="w-full !mb-0"
                    value={formData.title}
                    onChange={handleOnchange}
                />
                {formData.title === '' && isError && <p className="body4 !text-red-500 mt-2 h-[10px]">Workspace title is required</p>}
                <p className={cn('mb-3 body1 text-black-900', formData.title === '' && isError ? 'mt-[24px]' : 'mt-[42px]')}>Description</p>
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
                    placeholder="Enter your workspace description"
                />
            </div>
            <div className="flex justify-end mt-8">
                <Button
                    size="medium"
                    onClick={() => {
                        if (formData.title !== '') {
                            increaseStep();
                        } else {
                            setError(true);
                        }
                    }}
                >
                    Next
                </Button>
            </div>
        </div>
    );
    const StepTwoContent = (
        <div className="md:w-[454px] w-full  p-10 bg-white rounded">
            {AddWorkspaceHeader}
            <p className="mt-7 mb-8  h4 text-brand-900">Add workspace logo</p>
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
            <div className="flex justify-end mt-8 items-center">
                <Button size="medium" onClick={onClickDone} isLoading={isLoading || data?.isLoading}>
                    Done
                </Button>
            </div>
        </div>
    );

    if (isSuccess) return <FullScreenLoader />;
    return (
        <Layout showNavbar showAuthAccount={createWorkspace} isCustomDomain>
            <div className=" flex flex-col my-[40px] items-center">
                {stepCount === 0 && StepZeroContent}
                {stepCount === 1 && StepOneContent}
                {stepCount === 2 && StepTwoContent}
            </div>
        </Layout>
    );
}
