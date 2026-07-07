'use client';

import { FormEvent, useState } from 'react';

import { useRouter } from 'next/navigation';
import { useTranslation } from 'react-i18next';

import UploadLogo from '@Components/common/upload-logo';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import WorkspaceNameInputHandler from '@Components/onboarding/workspace-name-input-handler';
import AuthNavbar from '@app/components/auth/auth-navbar';
import { onBoarding } from '@app/constants/locales/onboarding-screen';
import { toastMessage } from '@app/constants/locales/toast-message';
import { UserStatus } from '@app/models/dtos/user-status';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { AppInput } from '@app/shadcn/components/ui/input';
import { Label } from '@app/shadcn/components/ui/label';
import { Textarea } from '@app/shadcn/components/ui/textarea';
import { selectAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateWorkspaceMutation, useLazyGetWorkspaceNameSuggestionsQuery, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';
import { InfoIcon } from 'lucide-react';

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

const OnboardingContainer = ({ workspace, createWorkspace }: onBoardingProps) => {
    const { toast } = useToast();
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const router = useRouter();
    const authStatus = useAppSelector(selectAuth);
    const user: UserStatus = !!authStatus ? authStatus : null;

    const [createWorkspaceRequest, data] = useCreateWorkspaceMutation();
    const [patchExistingWorkspace, { isLoading, isSuccess }] = usePatchExistingWorkspaceMutation();

    const workspaceName: string = (workspace?.workspaceName as string) === (workspace?.ownerId as string) ? '' : (workspace?.workspaceName as string);

    const [trigger] = useLazyGetWorkspaceNameSuggestionsQuery();

    const [formData, setFormData] = useState<FormDataDto>({
        title: createWorkspace ? '' : (user?.firstName || user?.lastName || user?.email?.split('@')[0]) + "'s Workspace",
        description: workspace?.description ?? '',
        workspaceLogo: workspace?.profileImage ?? null,
        workspaceName: createWorkspace ? '' : workspaceName
    });

    const [errors, setErrors] = useState<{ title?: string }>({});

    // Handle logo upload
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
            toast({
                description: response.error?.data || t(toastMessage.somethingWentWrong),
                variant: 'destructive'
            });
        }
        if (response.data) {
            toast({ description: t(toastMessage.workspaceUpdate).toString() });
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
        const response: any = await patchExistingWorkspace({ workspace_id: workspace?.id, body: updateFormData });
        if (response.error) {
            toast({
                description: response.error?.data || t(toastMessage.somethingWentWrong),
                variant: 'destructive'
            });
        }
        if (response.data) {
            toast({ description: t(toastMessage.workspaceUpdate).toString() });
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
        if (!!errors?.title && e.target.id === 'title') {
            setErrors({ ...errors, title: '' });
        }
    };

    const onSubmitForm = async (event: FormEvent) => {
        event.preventDefault();
        if (formData.title && formData.workspaceName) {
            await onClickDone();
        } else {
            if (!formData.title) setErrors({ ...errors, title: 'Please enter a workspace name' });
        }
    };

    const onWorkspaceTitleBlur = async (event: any) => {
        if (!event.target.value) {
            setErrors({ ...errors, title: 'Please enter a workspace name' });
            return;
        }
        if (createWorkspace && !formData.workspaceName) {
            const suggestion = await fetchSuggestionsForWorkspaceHandle(event.target.value || '');
            setFormData({ ...formData, workspaceName: suggestion });
        }
    };

    const fetchSuggestionsForWorkspaceHandle = async (text: string) => {
        if (!!text) {
            const request = {
                workspaceId: createWorkspace ? '' : workspace?.id,
                title: text.toLowerCase()
            };
            const { isSuccess, data } = await trigger(request);
            if (isSuccess) {
                if (data.includes(text)) {
                    return text;
                } else {
                    const suggestion = data[Math.floor(Math.random() * 4) + 1];
                    return suggestion;
                }
            }
        }
    };

    return (
        <div className="flex w-full flex-col items-center bg-white px-4 h-screen md:px-0">
            <AuthNavbar showPlans={false} showHamburgerIcon />
            <div className="mt-32 flex flex-col">
                <div className="h3-new">{t(onBoarding.addYourOrganization)}</div>
                <UploadLogo logoImageUrl={workspace?.profileImage ?? ''} className="mt-12" onUpload={handleUploadLogo} onRemove={handleRemoveLogo} />
                <form className="mt-12 w-full space-y-8 md:w-[541px] " onSubmit={onSubmitForm}>
                    {/* Workspace name input section */}
                    <div className="flex flex-col gap-1.5 w-full relative">
                        <Label htmlFor="title" className="text-sm font-medium ml-1 mb-1 text-gray-700">
                            Workspace name
                        </Label>
                        <AppInput
                            onBlur={onWorkspaceTitleBlur}
                            required
                            id="title"
                            placeholder="Enter name of your workspace"
                            value={formData.title}
                            onChange={handleOnchange}
                            className={!!errors?.title ? 'border-red-500 focus-visible:ring-red-500 w-full' : 'w-full'}
                        />
                        {/* Error message for workspace name */}
                        {!!errors?.title && (
                            <span className="flex items-center gap-1 text-xs text-red-600 absolute -bottom-6 left-1">
                                <InfoIcon className="h-3 w-3" /> {errors.title}
                            </span>
                        )}
                    </div>

                    {/* Workspace/Handle Name Input Section */}
                    <WorkspaceNameInputHandler formData={formData} setFormData={setFormData} handleOnChange={handleOnchange} createWorkspace={createWorkspace} />

                    {/* Description Textarea Section */}
                    <div className="flex flex-col gap-1.5 w-full">
                        <Label htmlFor="description" className="text-sm font-medium ml-1 mb-1 text-gray-700">
                            Add a workspace description
                        </Label>
                        <Textarea
                            id="description"
                            placeholder="Write Description"
                            value={formData.description}
                            onChange={handleOnchange}
                        />
                    </div>

                    <Button size="medium" className="w-full " type="submit" disabled={!formData.title || !formData.workspaceName}>
                        {t(onBoarding.addNowButton)}
                    </Button>
                </form>
            </div>
        </div>
    );
};

export default OnboardingContainer;
