import React, { useRef, useState } from 'react';

import { useRouter } from 'next/router';

import environments from '@app/configs/environments';
import Layout from '@app/layouts/_layout';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { useCreateWorkspaceMutation, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { checkHasCustomDomain } from '@app/utils/serverSidePropsUtils';

const SetUpWorkspace = (props: any) => {
    const [createWorkspace, { isLoading, isError }] = useCreateWorkspaceMutation();
    const existingWorkspace = usePatchExistingWorkspaceMutation();

    const [workspaceForm, setWorkspaceForm] = useState({
        title: '',
        workspace_name: '',
        description: '',
        profile_image: '',
        banner_image: ''
    });

    console.log(workspaceForm);

    const bannerImage = useRef(null);

    const handleSubmit = async (e: any) => {
        e.preventDefault();

        //creating a form data
        const formData = new FormData();
        formData.append('profile_image', workspaceForm.profile_image);
        formData.append('banner_image', workspaceForm.banner_image);
        formData.append('title', workspaceForm.title);
        formData.append('description', workspaceForm.description);
        formData.append('workspace_name', workspaceForm.workspace_name);

        console.log('formdata', formData);

        if (props.createWorkspace) {
            const data = await createWorkspace(formData).unwrap();
            console.log('create workspace: ', data);
        } else {
            const [patchExistingWorkspace] = existingWorkspace;
            const response = {
                workspace_id: props.workspace.id,
                body: formData
            };
            const data = await patchExistingWorkspace(response);
            console.log('patch workspace: ', data);
        }
    };

    const handleChange = (e: any) => {
        e.preventDefault();
        setWorkspaceForm({ ...workspaceForm, [e.target.name]: e.target.value });
    };

    const handleFileUpload = (e: any) => {
        e.preventDefault();
        const file = e.target.files[0];
        const reader = new FileReader();

        reader.onload = function () {
            //convert the file contents to a Uint8Array
            const binaryString: any = reader.result;
            if (!!binaryString && binaryString.length !== 0) {
                const binaryArray = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    binaryArray[i] = binaryString.charCodeAt(i);
                }

                // create a file object from the Uint8Array
                const fileObject = new Blob([binaryArray], { type: file.type });

                setWorkspaceForm({ ...workspaceForm, [e.target.name]: fileObject });
            }
        };
        reader.readAsBinaryString(file);
    };

    return (
        <Layout className="h-[100vh]" hideSignIn={true}>
            <div className="flex flex-col  items-center justify-center px-4 mt-10 py-8 mx-auto lg:py-0">
                <div className="w-full rounded-lg shadow-md md:mt-0 sm:max-w-lg xl:p-0">
                    <div className="p-6 space-y-4 md:space-y-6 sm:p-8">
                        <div className="flex gap-4">
                            <svg className="w-7 h-7" xmlns="http://www.w3.org/2000/svg" fill="#007aff" viewBox="0 0 640 512">
                                <path d="M308.5 135.3c7.1-6.3 9.9-16.2 6.2-25c-2.3-5.3-4.8-10.5-7.6-15.5L304 89.4c-3-5-6.3-9.9-9.8-14.6c-5.7-7.6-15.7-10.1-24.7-7.1l-28.2 9.3c-10.7-8.8-23-16-36.2-20.9L199 27.1c-1.9-9.3-9.1-16.7-18.5-17.8C173.7 8.4 166.9 8 160 8s-13.7 .4-20.4 1.2c-9.4 1.1-16.6 8.6-18.5 17.8L115 56.1c-13.3 5-25.5 12.1-36.2 20.9L50.5 67.8c-9-3-19-.5-24.7 7.1c-3.5 4.7-6.8 9.6-9.9 14.6l-3 5.3c-2.8 5-5.3 10.2-7.6 15.6c-3.7 8.7-.9 18.6 6.2 25l22.2 19.8C32.6 161.9 32 168.9 32 176s.6 14.1 1.7 20.9L11.5 216.7c-7.1 6.3-9.9 16.2-6.2 25c2.3 5.3 4.8 10.5 7.6 15.6l3 5.2c3 5.1 6.3 9.9 9.9 14.6c5.7 7.6 15.7 10.1 24.7 7.1l28.2-9.3c10.7 8.8 23 16 36.2 20.9l6.1 29.1c1.9 9.3 9.1 16.7 18.5 17.8c6.7 .8 13.5 1.2 20.4 1.2s13.7-.4 20.4-1.2c9.4-1.1 16.6-8.6 18.5-17.8l6.1-29.1c13.3-5 25.5-12.1 36.2-20.9l28.2 9.3c9 3 19 .5 24.7-7.1c3.5-4.7 6.8-9.5 9.8-14.6l3.1-5.4c2.8-5 5.3-10.2 7.6-15.5c3.7-8.7 .9-18.6-6.2-25l-22.2-19.8c1.1-6.8 1.7-13.8 1.7-20.9s-.6-14.1-1.7-20.9l22.2-19.8zM208 176c0 26.5-21.5 48-48 48s-48-21.5-48-48s21.5-48 48-48s48 21.5 48 48zM504.7 500.5c6.3 7.1 16.2 9.9 25 6.2c5.3-2.3 10.5-4.8 15.5-7.6l5.4-3.1c5-3 9.9-6.3 14.6-9.8c7.6-5.7 10.1-15.7 7.1-24.7l-9.3-28.2c8.8-10.7 16-23 20.9-36.2l29.1-6.1c9.3-1.9 16.7-9.1 17.8-18.5c.8-6.7 1.2-13.5 1.2-20.4s-.4-13.7-1.2-20.4c-1.1-9.4-8.6-16.6-17.8-18.5L583.9 307c-5-13.3-12.1-25.5-20.9-36.2l9.3-28.2c3-9 .5-19-7.1-24.7c-4.7-3.5-9.6-6.8-14.6-9.9l-5.3-3c-5-2.8-10.2-5.3-15.6-7.6c-8.7-3.7-18.6-.9-25 6.2l-19.8 22.2c-6.8-1.1-13.8-1.7-20.9-1.7s-14.1 .6-20.9 1.7l-19.8-22.2c-6.3-7.1-16.2-9.9-25-6.2c-5.3 2.3-10.5 4.8-15.6 7.6l-5.2 3c-5.1 3-9.9 6.3-14.6 9.9c-7.6 5.7-10.1 15.7-7.1 24.7l9.3 28.2c-8.8 10.7-16 23-20.9 36.2L315.1 313c-9.3 1.9-16.7 9.1-17.8 18.5c-.8 6.7-1.2 13.5-1.2 20.4s.4 13.7 1.2 20.4c1.1 9.4 8.6 16.6 17.8 18.5l29.1 6.1c5 13.3 12.1 25.5 20.9 36.2l-9.3 28.2c-3 9-.5 19 7.1 24.7c4.7 3.5 9.5 6.8 14.6 9.8l5.4 3.1c5 2.8 10.2 5.3 15.5 7.6c8.7 3.7 18.6 .9 25-6.2l19.8-22.2c6.8 1.1 13.8 1.7 20.9 1.7s14.1-.6 20.9-1.7l19.8 22.2zM464 400c-26.5 0-48-21.5-48-48s21.5-48 48-48s48 21.5 48 48s-21.5 48-48 48z" />
                            </svg>
                            <h1 className="text-xl font-bold leading-tight tracking-tight md:text-2xl text-gray-900">Set up your workspace</h1>
                        </div>
                        <form className="space-y-4 md:space-y-6" action="#">
                            <div className="">
                                <label htmlFor="title" className="block mb-2 text-md font-medium text-gray-900">
                                    Workspace title
                                </label>
                                <input type="text" onChange={handleChange} name="title" className="bg-gray-50 border-solid border-gray-300 text-gray-900 sm:text-sm rounded-lg block w-full p-2.5" placeholder="workspace title" required />
                            </div>
                            <div className="">
                                <label htmlFor="name" className="block mb-2 text-md font-medium text-gray-900">
                                    Workspace Name
                                </label>
                                <input type="text" onChange={handleChange} name="workspace_name" className="bg-gray-50 border-solid border-gray-300 text-gray-900 sm:text-sm rounded-lg block w-full p-2.5" placeholder="workspace name" required />
                            </div>
                            <div className="">
                                <label htmlFor="description" className="block mb-2 text-md font-medium text-gray-900">
                                    Workspace Description
                                </label>
                                <textarea name="description" onChange={handleChange} rows={3} className="bg-gray-50 border-solid border-gray-300 text-gray-900 sm:text-sm rounded-lg block w-full p-2.5" placeholder="workspace description" required />
                            </div>
                            <div className="max-w-xl mx-auto">
                                <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-gray-300" htmlFor="profile">
                                    Profile Photo
                                </label>
                                <input
                                    className="block w-full text-sm text-gray-900 border border-gray-300 rounded-md cursor-pointer bg-gray-50 file:rounded-l-md file:py-3 file:px-3 file:bg-gray-500 file:text-white file:border-none "
                                    id="profile"
                                    ref={bannerImage}
                                    onChange={handleFileUpload}
                                    type="file"
                                    name="profile_image"
                                />
                            </div>
                            <div className="max-w-xl mx-auto">
                                <label className="block mb-2 text-sm font-medium text-gray-900" htmlFor="cover">
                                    Cover Photo
                                </label>
                                <input
                                    className="block w-full text-sm text-gray-900 border border-gray-300 rounded-md cursor-pointer bg-gray-50 file:rounded-l-md file:py-3 file:px-3 file:bg-gray-500 file:text-white file:border-none "
                                    id="cover"
                                    onChange={handleFileUpload}
                                    name="banner_image"
                                    type="file"
                                />
                            </div>
                            <div className="flex gap-5">
                                <button
                                    type="submit"
                                    onClick={handleSubmit}
                                    className="w-full text-white bg-blue-700 hover:bg-primary-700 focus:ring-4 focus:outline-none focus:ring-primary-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-primary-600 dark:hover:bg-primary-700 dark:focus:ring-primary-800"
                                >
                                    Save
                                </button>
                                <button className="w-full border-[1px] text-gray-700 border-gray-300  hover:bg-primary-700 focus:ring-4 focus:outline-none focus:ring-primary-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-primary-600 dark:hover:bg-primary-700 dark:focus:ring-primary-800">
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </Layout>
    );
};

export default SetUpWorkspace;

export async function getServerSideProps(_context: any) {
    const { cookies } = _context.req;

    const hasCustomDomain = checkHasCustomDomain(_context);
    if (hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }

    let globalProps = await getGlobalServerSidePropsByWorkspaceName(_context).catch((e) => {});
    globalProps = globalProps.props;

    const auth = !!cookies.Authorization ? `Authorization=${cookies.Authorization}` : '';
    const refresh = !!cookies.RefreshToken ? `RefreshToken=${cookies.RefreshToken}` : '';

    const config = {
        method: 'GET',
        headers: {
            cookie: `${auth};${refresh}`
        }
    };

    try {
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e))?.payload?.content ?? null;
        if (user?.user?.roles?.includes('FORM_CREATOR')) {
            const userWorkspaceResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/mine`, config);
            const userWorkspace = (await userWorkspaceResponse?.json().catch((e: any) => e))?.payload?.content ?? null;
            const { id } = userWorkspace[0];

            if (!userWorkspace || userWorkspace.length < 1) {
                return {
                    props: {
                        createWorkspace: true
                    }
                };
            }
            return {
                props: {
                    ...globalProps
                }
            };
        }
    } catch (e) {
        return {
            props: {
                error: true
            }
        };
    }

    return {
        props: {}
    };
}
