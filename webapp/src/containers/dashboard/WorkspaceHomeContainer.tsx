import React, { SyntheticEvent, useMemo, useRef } from 'react';
import { useState } from 'react';

import { useRouter } from 'next/router';

import ModeEditIcon from '@mui/icons-material/ModeEdit';
import SaveIcon from '@mui/icons-material/Save';
import { Box, CircularProgress, Dialog, Typography } from '@mui/material';
import Modal from '@mui/material/Modal';
import { maxHeight } from '@mui/system';
import html2canvas from 'html2canvas';
import AvatarEditor from 'react-avatar-editor';
import { toast } from 'react-toastify';
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch';

import FormsAndSubmissionsTabContainer from '@app/components/forms-and-submisions-tabs/forms-and-submisisons-tab-container';
import { HomeIcon } from '@app/components/icons/home';
import { Logout } from '@app/components/icons/logout-icon';
import WorkspaceFooter from '@app/components/layout/workspace-footer';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Image from '@app/components/ui/image';
import WorkspaceHeader from '@app/components/workspace/workspace-header';
import environments from '@app/configs/environments';
import { ToastId } from '@app/constants/toastId';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { authApi, useGetStatusQuery, useLazyGetLogoutQuery } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';

interface IDashboardContainer {
    workspace: WorkspaceDto;
    isCustomDomain: boolean;
}

const style = {
    position: 'absolute' as 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: 400,
    bgcolor: 'background.paper',
    border: '2px solid #000',
    boxShadow: 24,
    p: 4
};

interface BannerImageComponentPropType {
    workspace: WorkspaceDto;
    isFormCreator: () => Boolean;
}

const BannerImageComponent = (props: BannerImageComponentPropType) => {
    const { workspace, isFormCreator } = props;
    const router = useRouter();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const [bannerImage, setBannerImage] = useState('');
    const bannerImageInputRef = useRef<HTMLInputElement>(null);

    if (isLoading) {
        return (
            <div className="h-full bg-black opacity-70 text-white flex flex-col justify-center items-center">
                <CircularProgress />
                <p>Uploading Image...</p>
            </div>
        );
    }

    const onuploadFileChange = (e: any) => {
        if (!e.target && !e.target.files && !Array.isArray(e.target.files)) return;
        setBannerImage(URL.createObjectURL(e.target.files[0]));
    };

    const onClickFileUploadButton = () => {
        if (!!bannerImageInputRef.current) {
            bannerImageInputRef.current.click();
        }
    };

    const onClickFileSaveButton = (e: any) => {
        const croppedImageDiv: any = document.getElementsByClassName('react-transform-wrapper')[0];
        if (!croppedImageDiv) return;
        html2canvas(croppedImageDiv).then((canvas: HTMLCanvasElement) => {
            canvas.toBlob(async (blob: any) => {
                const file = new File([blob], 'bannerimage.png', { type: blob.type });
                const formData = new FormData();
                formData.append('banner_image', file);
                const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
                if (response.error) {
                    toast('Something went wrong', { toastId: ToastId.ERROR_TOAST });
                }
                if (response.data) {
                    toast('Workspace Updated', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
                    setBannerImage('');
                    router.push(router.asPath, undefined);
                }
            });
        });
    };

    function ConditionalImageRendering() {
        switch (!!bannerImage) {
            case false:
                return <Image src={workspace.bannerImage} priority layout="fill" objectFit="contain" objectPosition="center" alt={workspace?.title} />;
            case true:
                return (
                    <TransformWrapper centerOnInit>
                        <TransformComponent wrapperStyle={{ maxHeight: 'calc(100vh)', maxWidth: '100%', height: '100%', width: '100%' }}>
                            <img src={bannerImage} alt="test" />
                        </TransformComponent>
                    </TransformWrapper>
                );
            default:
                return <></>;
        }
    }

    return (
        <div className="relative overflow-hidden h-44 w-full md:h-80 xl:h-[380px] bannerdiv">
            <ConditionalImageRendering />
            {isFormCreator() && (
                <div className="absolute bottom-1 right-4 hidden editbannerdiv">
                    <div className="flex justify-between">
                        <div className="p-1 px-2 ml-2 my-19 bg-blue-600 hover:bg-blue-700 cursor-pointer rounded-md" onClick={onClickFileUploadButton}>
                            <ModeEditIcon className="!w-5 !h-5 text-white" />
                            <span className="ml-1 text-white">update image</span>
                        </div>

                        {!!bannerImage && (
                            <div className="p-1 px-2 ml-2 my-19 bg-blue-600 hover:bg-blue-700 cursor-pointer rounded-md" onClick={onClickFileSaveButton}>
                                <SaveIcon className="!w-5 !h-5 text-white" />
                                <span className="ml-1 text-white">save image</span>
                            </div>
                        )}
                    </div>
                </div>
            )}
            <input ref={bannerImageInputRef} type="file" accept="image/*" className="hidden" onChange={onuploadFileChange} />
        </div>
    );
};

// const ProfileImageComponent = (props: any) => {
//     const { workspace, isFormCreator } = props;
//     const profileInputRef = useRef<HTMLInputElement>(null);
//     const [uploadImage, setUploadImage] = useState('');

//     return (
//         <div className="product-box">
//             <div className="bannerdiv product-image bg-white absolute border-[1px] border-neutral-300 hover:border-neutral-400 rounded-full z-10 h-24 w-24 sm:h-32 sm:w-32 md:h-40 md:w-40 xl:h-40 xl:w-40 2xl:h-[180px] 2xl:w-[180px] overflow-hidden -top-12 sm:-top-16 md:-top-20 xl:-top-[88px] 2xl:-top-24">
//                 {workspace.profileImage && <Image src={workspace.profileImage} layout="fill" objectFit="contain" alt={workspace.title} />}
//                 <div className="absolute hidden bg-gray-600 p-2 cursor-pointer opacity-20 text-gray-500 bottom-2 left-12 opacity-25 editbannerdiv" onClick={() => !!profileInputRef.current && profileInputRef.current.click()}>
//                     <p>Update</p>
//                 </div>
//                 <input ref={profileInputRef} type="file" accept="image/*" className="hidden" onChange={handleProfileUpload} />
//                 <Dialog open={!!uploadImage} onClose={() => setUploadImage('')} aria-labelledby="modal-modal-title" aria-describedby="modal-modal-description">
//                     <div className="p-4">
//                         <AvatarEditor ref={profileEditorRef} image={profileUploadImage} width={250} height={250} border={50} borderRadius={10000} color={[0, 0, 0, 0.6]} scale={profileScale} rotate={0} />
//                         <span className="text-sm">Zoom:</span>
//                         <input name="scale" type="range" onChange={(e) => setProfileScale(parseFloat(e.target.value))} min={1} max={4} step="0.01" defaultValue={1} />
//                         <div>
//                             <Button variant="solid" color="info" className="shadow-none" onClick={handleProfileUpdateClick}>
//                                 Update Profile
//                             </Button>
//                         </div>
//                     </div>
//                 </Dialog>
//             </div>
//         </div>
//     );
// };

export default function DashboardContainer({ workspace, isCustomDomain }: IDashboardContainer) {
    const [trigger] = useLazyGetLogoutQuery();

    const authStatus = useGetStatusQuery('status');
    const { openModal } = useModal();

    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select('status'), []);
    const selectGetStatus = useAppSelector(statusQuerySelect);

    const inputRef: any = useRef(null);

    const router = useRouter();

    const profileEditorRef = useRef(null);

    const profileInputRef = useRef(null);

    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

    const [uploadedBannerImage, setUploadedBannerImage] = useState<any>('');
    const [profileUploadImage, setProfileUploadImage] = useState<any>(null);

    const [profileImageEditMode, setProfileImageEditMode] = useState(false);

    const [profileScale, setProfileScale] = useState(1);

    if (!workspace || authStatus.isLoading) return <FullScreenLoader />;

    function isFormCreator(): Boolean {
        return selectGetStatus.data.payload.content.user.id === workspace.ownerId;
    }

    const handleLogout = async () => {
        trigger().finally(() => {
            authStatus.refetch();
        });
    };

    const handleCheckMyData = () => {
        openModal('LOGIN_VIEW', { isCustomDomain: true });
    };

    const handleProfileUpdateClick = async () => {
        // This returns a HTMLCanvasElement, it can be made into a data URL or a blob,
        // drawn on another canvas, or added to the DOM.
        const dataUrl = profileEditorRef.current.getImage().toDataURL();
        const result = await fetch(dataUrl);
        const blob = await result.blob();
        const file = new File([blob], 'profileImage.png', { type: blob.type });
        const formData = new FormData();
        formData.append('profile_image', file);
        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
        if (response.error) {
            toast('Something went wrong!!!', { toastId: ToastId.ERROR_TOAST });
        }
        if (response.data) {
            toast('Workspace Updated!!!', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
            setUploadedBannerImage('');
            router.push(router.asPath, undefined);
        }
    };

    const handleProfileUpload = (e: any) => {
        setProfileUploadImage(e.target.files[0]);
    };

    const Footer = () => {
        return (
            <div className="absolute left-0 bottom-0 w-full flex flex-col justify-start md:flex-row md:justify-between md:items-center px-6 sm:px-8 lg:px-12 py-2 border-t-[1.5px] border-[#eaeaea] bg-transparent drop-shadow-main mb-0">
                <div className="flex justify-between mb-4">
                    <ActiveLink target={'_blank'} className="mt-6 md:mt-0 text-sm md:text-lg mr-6 hover:text-gray-600" href={workspace.terms_of_service_url ?? ''}>
                        Terms of service
                    </ActiveLink>
                    <ActiveLink target={'_blank'} className="mt-6 md:mt-0 text-sm md:text-lg hover:text-gray-600" href={workspace.privacy_policy_url ?? ''}>
                        Privacy Policy
                    </ActiveLink>
                </div>
                {isCustomDomain && (
                    <div className="mb-2">
                        <p>Powered by</p>
                        <Logo className="!text-lg" />
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="relative min-h-screen">
            <div className="relative overflow-hidden h-44 w-full md:h-80 xl:h-[380px] bannerdiv">
                <BannerImageComponent workspace={workspace} isFormCreator={isFormCreator} />
            </div>
            <Layout className="!pt-0 relative min-h-screen bg-[#FBFBFB] pb-40">
                <div className="flex justify-between items-center">
                    <div className="product-box">
                        <div className="bannerdiv product-image bg-white absolute border-[1px] border-neutral-300 hover:border-neutral-400 rounded-full z-10 h-24 w-24 sm:h-32 sm:w-32 md:h-40 md:w-40 xl:h-40 xl:w-40 2xl:h-[180px] 2xl:w-[180px] overflow-hidden -top-12 sm:-top-16 md:-top-20 xl:-top-[88px] 2xl:-top-24">
                            {workspace.profileImage && <Image src={workspace.profileImage} layout="fill" objectFit="contain" alt={workspace.title} />}
                            <div className="absolute hidden bg-white cursor-pointer opacity-20 text-gray-500 bottom-2 left-12 opacity-25 editbannerdiv" onClick={() => profileInputRef.current.click()}>
                                <p>Update</p>
                                {/* <ModeEditIcon className="!w-5 !h-5 text-blue-500" /> */}
                            </div>
                            <input ref={profileInputRef} type="file" accept="image/*" className="hidden" onChange={handleProfileUpload} />
                            <Dialog open={!!profileUploadImage} onClose={() => setProfileUploadImage('')} aria-labelledby="modal-modal-title" aria-describedby="modal-modal-description">
                                <div className="p-4">
                                    <AvatarEditor ref={profileEditorRef} image={profileUploadImage} width={250} height={250} border={50} borderRadius={10000} color={[0, 0, 0, 0.6]} scale={profileScale} rotate={0} />
                                    <span className="text-sm">Zoom:</span>
                                    <input name="scale" type="range" onChange={(e) => setProfileScale(parseFloat(e.target.value))} min={1} max={4} step="0.01" defaultValue={1} />
                                    <div>
                                        <Button variant="solid" color="info" className="shadow-none" onClick={handleProfileUpdateClick}>
                                            Update Profile
                                        </Button>
                                    </div>
                                </div>
                            </Dialog>
                        </div>
                    </div>
                    <div className="mt-2 mb-0 flex items-center">
                        {!!selectGetStatus.error ? (
                            <Button variant="solid" className="ml-3 !px-8 !rounded-xl !bg-blue-500" onClick={handleCheckMyData}>
                                Check My Data
                            </Button>
                        ) : (
                            <>
                                {selectGetStatus.data?.payload?.content.user.id === workspace.ownerId && (
                                    <a
                                        target="_blank"
                                        referrerPolicy="no-referrer"
                                        href={`${environments.CLIENT_HOST.includes('localhost') ? 'http://' : 'https://'}${environments.CLIENT_HOST}/${workspace.workspaceName}/dashboard`}
                                        className="rounded-xl mr-5 !bg-blue-600 z-10 !text-white px-5 py-3"
                                        rel="noreferrer"
                                    >
                                        <div className=" flex space-x-4">
                                            <HomeIcon className="w-[20px] h-[20px]" />
                                            <div className="hidden md:flex">Go To Dashboard</div>
                                        </div>
                                    </a>
                                )}
                                {!!selectGetStatus.data.payload.content.user.sub && (
                                    <>
                                        <div className="px-5 py-3 bg-gray-100 md:hidden mr-2 md:mr-5 text-gray-800 rounded-xl capitalize">{selectGetStatus.data.payload.content.user.sub[0]}</div>
                                        <div className="py-3 px-5 hidden sm:flex rounded-full text-gray-700 border-solid italic border-[1px] border-[#eaeaea]">{selectGetStatus.data.payload.content.user.sub}</div>
                                    </>
                                )}
                                <Button variant="solid" className="ml-3 !px-3 !py-6 !rounded-xl !bg-[#ffe0e0]" onClick={handleLogout}>
                                    <span className="w-full flex gap-2 items-center justify-center">
                                        <Logout height={20} width={20} className="!rounded-xl !text-[#e60000]" />
                                        <span className="!text-[#e60000] hidden md:flex">Sign off</span>
                                    </span>
                                </Button>
                            </>
                        )}
                    </div>
                </div>
                <WorkspaceHeader workspace={workspace} />
                <FormsAndSubmissionsTabContainer workspace={workspace} workspaceId={workspace.id} showResponseBar={!!selectGetStatus.error} />
                <WorkspaceFooter workspace={workspace} isCustomDomain={isCustomDomain} />
            </Layout>
        </div>
    );
}
