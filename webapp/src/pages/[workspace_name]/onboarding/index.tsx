import React, { useRef, useState } from 'react';

import { useRouter } from 'next/router';

import _ from 'lodash';

import { ChevronLeft, Height } from '@mui/icons-material';
import { TextField } from '@mui/material';
import cn from 'classnames';
import { toast } from 'react-toastify';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { ToastId } from '@app/constants/toastId';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectAuthStatus } from '@app/store/auth/selectors';
import { selectAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormsQuery, useGetWorkspaceStatsQuery, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

interface addWorkspaceFormProviderDtos {
    title: string;
    description: string;
    workspaceLogo: any;
}

interface onBoardingProps {
    workspace: WorkspaceDto;
}

export default function Onboarding({ workspace }: onBoardingProps) {
    const router = useRouter();
    const authStatus = useAppSelector(selectAuth);

    const user: any = !!authStatus ? authStatus : null;
    let workspaceLogoRef = useRef<HTMLInputElement>(null);
    const dispatch = useAppDispatch();
    const [isError, setError] = useState(false);
    const profileName = _.capitalize(user?.first_name) + ' ' + _.capitalize(user?.last_name);
    const [stepCount, setStepCount] = useState(0);
    const [patchExistingWorkspace, { isLoading, isSuccess }] = usePatchExistingWorkspaceMutation();
    const [formProvider, setFormProvider] = useState<addWorkspaceFormProviderDtos>({
        title: '',
        description: '',
        workspaceLogo: null
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
            setFormProvider({
                ...formProvider,
                workspaceLogo: image
            });
        }
    };
    const handleOnchange = (e: any) => {
        console.log(e);
        setFormProvider({
            ...formProvider,
            [e.target.id]: e.target.value
        });
    };

    const updateWorkspaceDetails = async () => {
        const formData = new FormData();
        if (formProvider.workspaceLogo) {
            formData.append('profile_image', formProvider.workspaceLogo);
        }
        formData.append('title', formProvider.title);
        formData.append('description', formProvider.description);
        console.log(formData);
        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
        if (response.error) {
            toast('Something went wrong', { toastId: ToastId.ERROR_TOAST });
        }
        if (response.data) {
            toast('Workspace Updated', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
            dispatch(setWorkspace(response.data));
            router.replace(`/${workspace.workspaceName}/dashboard`);
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
                Create A Workspace
            </Button>
            <p className="body2 !text-black-600 italic">It will only take few minutes</p>
        </div>
    );
    const AddWorkspaceHeader = (
        <div className="flex justify-between items-center">
            <div className=" cursor-pointer hover:bg-blue-200 rounded" onClick={decreaseStep}>
                <ChevronLeft className="h-6 w-6" />
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
                <TextField
                    InputProps={{
                        sx: {
                            height: '46px',
                            borderColor: '#0764EB !important'
                        }
                    }}
                    id="title"
                    error={formProvider.title === '' && isError}
                    placeholder="Eg. Google"
                    className="w-full"
                    value={formProvider.title}
                    onChange={handleOnchange}
                />
                {formProvider.title === '' && isError && <p className="body4 !text-red-500 mt-2 h-[10px]">Workspace title is required</p>}
                <p className={cn('mb-3 body1 text-black-900', formProvider.title === '' && isError ? 'mt-[24px]' : 'mt-[42px]')}>Description</p>
                <textarea
                    id="description"
                    name="description"
                    value={formProvider.description}
                    rows={4}
                    onChange={handleOnchange}
                    className=" border-solid border-gray-300 text-gray-900 body3 rounded block w-full p-2.5"
                    placeholder="Add your description"
                    required
                />
            </div>
            <div className="flex justify-end mt-8">
                <Button
                    size="medium"
                    onClick={() => {
                        if (formProvider.title !== '') {
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
            <div className="flex md:flex-row flex-col gap-4 items-center">
                <AuthAccountProfileImage image={formProvider.workspaceLogo && URL.createObjectURL(formProvider.workspaceLogo)} name={profileName} size={143} typography="h1" />
                <div className="flex flex-col justify-center md:items-start items-center">
                    <p className="body3 mb-5 !text-black-700 md:text-start text-center">Make sure your image is less than 100MB</p>
                    <input type="file" accept="image/*" className="opacity-0 h-0 w-0" ref={workspaceLogoRef} onChange={handleFile} />
                    <Button size="small" variant="ghost" className="!text-brand-500 hover:!bg-brand-200 !bg-white !border-brand-300" onClick={() => workspaceLogoRef.current?.click()}>
                        Upload
                    </Button>
                </div>
            </div>
            <div className="flex justify-end mt-8 items-center">
                <Button size="medium" onClick={updateWorkspaceDetails} isLoading={isLoading}>
                    Done
                </Button>
            </div>
        </div>
    );
    if (isSuccess) return <FullScreenLoader />;
    return (
        <Layout showNavbar showAuthAccount={false}>
            <div className=" flex flex-col my-[40px] items-center">
                {stepCount === 0 && StepZeroContent}
                {stepCount === 1 && StepOneContent}
                {stepCount === 2 && StepTwoContent}
            </div>
        </Layout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
