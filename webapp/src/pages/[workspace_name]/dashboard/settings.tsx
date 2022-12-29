import { useEffect, useState } from 'react';

import { TextField } from '@mui/material';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import Layout from '@app/components/sidebar/layout';
import Button from '@app/components/ui/button/button';
import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetAllMineWorkspacesQuery, useLazyGetWorkspaceQuery, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function MySettings(props: any) {
    // fetched from the props
    const { bannerImage, customDomain, description, id, ownerId, profileImage, title, workspaceName } = props.workspace;

    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const [trigger] = useLazyGetWorkspaceQuery();
    const existingWorkspace = useAppSelector((state) => state.workspace);

    const dispatch = useDispatch();
    const [workspaceForm, setWorkspaceForm] = useState({ title: '', custom_domain: '', workspace_name: '', description: '', profile_image: '', banner_image: '' });

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

    const handleSaveCustomDomain = () => {
        console.log('custom domain saved!');
    };

    const SubTitleRenderer = ({ title, description }: any) => {
        return (
            <div className={` pb-4 border-b-gray-200 mt-6 mb-4 border-b-[1px] w-2/3 `}>
                <h1 className="text-2xl font-bold text-black">{title}</h1>
                {!!description && <p className="text-gray-600">{description}</p>}
            </div>
        );
    };

    const handleFileUpload = (e: any) => {
        e.preventDefault();
        const file = e.target.files[0];

        setWorkspaceForm({ ...workspaceForm, [e.target.name]: file });

        // const reader = new FileReader();

        // reader.onload = function () {
        //     //convert the file contents to a Uint8Array
        //     const binaryString = reader.result;
        //     if (!!binaryString && binaryString.length !== 0) {
        //         const binaryArray = new Uint8Array(binaryString.length);
        //         for (let i = 0; i < binaryString.length; i++) {
        //             binaryArray[i] = binaryString.charCodeAt(i);
        //         }

        //         // create a file object from the Uint8Array
        //         const fileObject = new Blob([binaryArray], { type: file.type });

        //         setWorkspaceForm({ ...workspaceForm, [e.target.name]: fileObject });
        //     }
        // };
        // reader.readAsBinaryString(file);
    };

    const handleUpdateProfile = async (e: any) => {
        e.preventDefault();

        if (!!handleValidation(workspaceForm.workspace_name, true) || !!handleValidation(workspaceForm.title, false)) return;

        const formData = new FormData();
        formData.append('profile_image', workspaceForm.profile_image);
        formData.append('banner_image', workspaceForm.banner_image);
        formData.append('title', workspaceForm.title);
        formData.append('description', workspaceForm.description);
        formData.append('workspace_name', workspaceForm.workspace_name);

        if (!id) return;

        const response = {
            workspace_id: id,
            body: formData
        };
        const data = await patchExistingWorkspace(response);
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
            <h1 className="mb-2 font-medium">Enter your custom domain</h1>
            <div className="w-full  md:w-2/3 h-[50px]">
                <div className="flex flex-row gap-6 items-center">
                    <div className=" flex flex-col h-[50px] justify-between w-full">
                        <TextField size="medium" name="custom_domain" placeholder="Custom-domain (e.g. https://forms.bettercollected.com)" value={workspaceForm.custom_domain} onChange={handleChange} className={`w-full`} />
                        {/* <div className={`text-red-500 text-sm`}>{error && 'Custom Domain cannot contain spaces.'}</div> */}
                    </div>
                    <Button className="!bg-blue-600 h-[50px]" onClick={handleSaveCustomDomain}>
                        Save
                    </Button>
                </div>
            </div>
            <form>
                <SubTitleRenderer title={'Workspace Information'} description={'Update your workspace profile'} />
                <div className="w-full md:w-2/3 h-[50px] pb-4">
                    <div className="mb-10">
                        <h1 className="text-lg">Workspace title</h1>
                        <div className=" flex flex-col h-[50px] justify-between w-full">
                            <TextField
                                error={!!handleValidation(workspaceForm.title, false)}
                                helperText={handleValidation(workspaceForm.title, false)}
                                size="medium"
                                name="title"
                                placeholder="Enter your workspace title"
                                value={workspaceForm.title}
                                onChange={handleChange}
                                className={`w-full`}
                            />
                        </div>
                    </div>

                    <div className="mb-10">
                        <h1 className="text-lg">Workspace Handle</h1>
                        <div className=" flex flex-col h-[50px] justify-between w-full">
                            <TextField
                                error={!!handleValidation(workspaceForm.workspace_name, true)}
                                helperText={handleValidation(workspaceForm.workspace_name, true)}
                                value={workspaceForm.workspace_name}
                                size="medium"
                                name="workspace_name"
                                placeholder="Enter your workspace name"
                                onChange={handleChange}
                                className={`w-full`}
                            />
                            {/* <div className={`text-red-500 text-sm`}>{error && 'Custom Domain cannot contain spaces.'}</div> */}
                        </div>
                    </div>

                    <div className="mb-10">
                        <h1 className="text-lg">Workspace Description</h1>
                        <textarea
                            name="description"
                            value={workspaceForm.description}
                            onChange={handleChange}
                            rows={3}
                            className=" border-solid border-gray-300 text-gray-900 sm:text-sm rounded-lg block w-full p-2.5"
                            placeholder="Enter about your workspace"
                            required
                        />
                    </div>

                    <div className="mb-10">
                        <label className="block text-xl mb-2 font-medium text-gray-900 dark:text-gray-300" htmlFor="profile">
                            Profile Photo
                        </label>
                        <input
                            accept="image/png, image/jpeg"
                            className="block w-full text-sm text-gray-900 border border-gray-300 rounded-md cursor-pointer bg-gray-50 file:rounded-l-md file:py-3 file:px-3 file:bg-gray-500 file:text-white file:border-none "
                            id="profile"
                            // value={!workspaceForm.profile_image ? null : workspaceForm.profile_image}
                            onChange={handleFileUpload}
                            type="file"
                            name="profile_image"
                        />
                    </div>

                    <div className="mb-10">
                        <label className="block text-xl mb-2 font-medium text-gray-900 dark:text-gray-300" htmlFor="profile">
                            Banner Photo
                        </label>
                        <input
                            accept="image/png, image/jpeg"
                            className="block w-full text-sm text-gray-900 border border-gray-300 rounded-md cursor-pointer bg-gray-50 file:rounded-l-md file:py-3 file:px-3 file:bg-gray-500 file:text-white file:border-none "
                            id="profile"
                            // value={!workspaceForm.banner_image ? null : workspaceForm.banner_image}
                            onChange={handleFileUpload}
                            type="file"
                            name="banner_image"
                        />
                    </div>

                    <Button isLoading={isLoading} type={'submit'} className="w-full md:w-auto !bg-blue-600 h-[50px] mb-10" onClick={handleUpdateProfile}>
                        Update workspace profile
                    </Button>
                </div>
            </form>
        </Layout>
    );
}

export async function getServerSideProps(_context: any) {
    const { cookies } = _context.req;
    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;

    if (globalProps.hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }
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
        if (!user?.user?.roles?.includes('FORM_CREATOR')) {
            return {
                redirect: {
                    permanent: false,
                    destination: '/login'
                }
            };
        } else {
            const userWorkspaceResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/mine`, config);
            const userWorkspace = (await userWorkspaceResponse?.json().catch((e: any) => e))?.payload?.content ?? null;
            if (!userWorkspace || userWorkspace.length < 1) {
                return {
                    redirect: {
                        permanent: false,
                        destination: `/setupWorkspace`
                    }
                };
            }
            const { id } = userWorkspace[0];
            return {
                props: {
                    ...globalProps
                }
            };
        }
    } catch (e) {
        return {
            redirect: {
                permanent: false,
                destination: '/login'
            }
        };
    }
}
