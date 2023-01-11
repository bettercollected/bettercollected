import React, { useEffect, useRef, useState } from 'react';

import { TextField } from '@mui/material';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { WorkspaceDangerZoneSettings } from '@app/components/settings/workspace/workspace-danger-zone-settings';
import { WorkspaceInformationSettings } from '@app/components/settings/workspace/workspace-information-settings';
import Layout from '@app/components/sidebar/layout';
import Button from '@app/components/ui/button/button';
import Image from '@app/components/ui/image';
import environments from '@app/configs/environments';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceQuery, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function MySettings(props: any) {
    const { bannerImage, customDomain, description, id, profileImage, title, workspaceName } = props.workspace;
    const imageRef = useRef<any>();

    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

    const [trigger] = useLazyGetWorkspaceQuery();
    const existingWorkspace = useAppSelector((state) => state.workspace);

    const dispatch = useDispatch();
    const [workspaceForm, setWorkspaceForm] = useState({
        title: '',
        custom_domain: '',
        workspace_name: '',
        description: '',
        profile_image: null,
        banner_image: null
    });

    useEffect(() => {
        setWorkspaceForm({
            title: title,
            workspace_name: workspaceName,
            description: description,
            profile_image: profileImage,
            banner_image: bannerImage,
            custom_domain: !!customDomain ? customDomain : ''
        });
    }, []);

    const handleValidation = (value: any, requireWhiteSpaceValidation: boolean) => {
        if (value.length === 0) return 'Field cannot be empty';
        if (requireWhiteSpaceValidation) {
            if (/\s/g.test(value)) return 'Field cannot have whitespaces';
        }
        return '';
    };

    const Header = () => {
        return (
            <div className="w-full flex justify-between items-center pb-4 border-b-gray-200 mb-4 border-b-[1px]">
                <div>
                    <h1 className="font-semibold text-2xl">Settings</h1>
                    <p className="text-gray-600"> Manage your workspace settings and preferences.</p>
                </div>
            </div>
        );
    };

    const handleChange = (e: any) => {
        e.preventDefault();
        setWorkspaceForm({ ...workspaceForm, [e.target.name]: e.target.value });
    };

    const SubTitleRenderer = ({ title, description }: any) => {
        return (
            <div className={` pb-4 border-b-gray-200 mt-6 mb-4 border-b-[1px] w-2/3 `}>
                <h1 className="text-2xl font-bold text-black">{title}</h1>
                {!!description && <p className="text-gray-600">{description}</p>}
            </div>
        );
    };

    const handleUpdateCustomDomain = async (e: any) => {
        if (!!handleValidation(workspaceForm.custom_domain, false)) return;
        const formData = new FormData();
        formData.append('custom_domain', workspaceForm.custom_domain);
        const response = {
            workspace_id: id,
            body: formData
        };
        const data: any = await patchExistingWorkspace(response);
        if (!data.error) {
            toast.info('Updated workspace info!');
            // update the workspace info to client side.
            const workspaceId = existingWorkspace.id;
            const data = await trigger(workspaceId);
            const workspace = data.data;
            dispatch(setWorkspace(workspace));
        } else {
            toast.error('Something went wrong!');
        }
    };

    // this method is used to check if the image obtained is a image url or a file object
    const checkIfTheImageUrlIsObjectOrLink = (srcContent: any) => {
        if (!srcContent) return;
        if (srcContent.constructor === File) {
            // image is a file object
            imageRef.current = URL.createObjectURL(srcContent);
            return imageRef.current;
        } else if (typeof srcContent === 'string') {
            // image is a url string
            return srcContent;
        }
    };

    const handleFileUpload = (e: any) => {
        e.preventDefault();
        URL.revokeObjectURL(imageRef.current);
        const file = e.target.files[0];
        setWorkspaceForm({ ...workspaceForm, [e.target.name]: file });
    };

    const handleUpdateProfile = async (e: any) => {
        e.preventDefault();
        if (!id) return;

        if (!!handleValidation(workspaceForm.workspace_name, true) || !!handleValidation(workspaceForm.title, false)) return;

        const { profile_image, banner_image, title, description, workspace_name }: any = workspaceForm;

        const formData = new FormData();
        if (!!profile_image && profile_image.constructor === File) {
            formData.append('profile_image', profile_image);
        }
        if (!!banner_image && banner_image.constructor === File) {
            formData.append('banner_image', banner_image);
        }
        !!title && formData.append('title', workspaceForm.title);
        formData.append('description', workspaceForm.description);
        !!workspace_name && formData.append('workspace_name', workspaceForm.workspace_name);
        const response = {
            workspace_id: id,
            body: formData
        };
        const data: any = await patchExistingWorkspace(response);
        if (!data.error) {
            toast.info('Updated workspace info!');
            // update the workspace info to client side.
            const workspaceId = existingWorkspace.id;
            const data = await trigger(workspaceId);
            const workspace = data.data;
            dispatch(setWorkspace(workspace));
        } else {
            toast.error('Something went wrong!');
        }
    };

    return (
        <Layout>
            <Header />
            <WorkspaceInformationSettings />
            <WorkspaceDangerZoneSettings />
        </Layout>
    );
}

export async function getServerSideProps(_context: any) {
    return await getAuthUserPropsWithWorkspace(_context);
}
