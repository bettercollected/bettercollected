import React, { BaseSyntheticEvent, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { Popover, TextField } from '@mui/material';
import { ChromePicker } from 'react-color';
import { toast } from 'react-toastify';

import Button from '@app/components/ui/button';
import Image from '@app/components/ui/image';
import environments from '@app/configs/environments';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import DynamicContainer from '@app/containers/DynamicContainer';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation, usePatchThemeMutation } from '@app/store/workspaces/api';
import { BrandColor, setWorkspace } from '@app/store/workspaces/slice';

interface PatchRequestType {
    title: string;
    description: string;
    banner_image?: string;
    profile_image?: string;
}

const SubTitleRenderer = ({ title, description }: any) => {
    return (
        <div className={` pb-4 border-b-gray-200 mt-6 mb-4 border-b-[1px] w-2/3 `}>
            <h1 className="text-2xl font-bold text-black">{title}</h1>
            {!!description && <p className="text-gray-600">{description}</p>}
        </div>
    );
};
export default function SettingsProfile() {
    const dispatch = useAppDispatch();
    const router = useRouter();
    const workspace = useAppSelector((state) => state.workspace);
    const { t } = useTranslation();

    const [patchReq, setPatchReq] = useState<PatchRequestType>({
        title: workspace.title,
        description: workspace.description
    });
    const [bannerImage, setBannerImage] = useState(!!workspace.bannerImage ? workspace.bannerImage : '/empty_banner.png');
    const [profileImage, setProfileImage] = useState(!!workspace.profileImage ? workspace.profileImage : '/empty_profile.png');

    const [brandColor, setBrandColor] = useState<BrandColor>({
        primary_color: workspace?.theme?.primary_color ?? '#fff',
        accent_color: workspace?.theme?.accent_color ?? '#fff',
        text_color: workspace?.theme?.text_color ?? '#fff'
    });

    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const [patchTheme] = usePatchThemeMutation();

    const [primaryEl, setPrimaryEl] = React.useState<HTMLButtonElement | null>(null);
    const [accentEl, setAccentEl] = React.useState<HTMLButtonElement | null>(null);
    const [textEl, setTextEl] = React.useState<HTMLButtonElement | null>(null);

    const openPrimary = Boolean(primaryEl);
    const openAccent = Boolean(accentEl);
    const openText = Boolean(textEl);

    const onChangeBannerImage = (event: BaseSyntheticEvent) => {
        if (event.target.files && event.target.files.length > 0) {
            setPatchReq({
                ...patchReq,
                banner_image: event.target.files[0]
            });
            setBannerImage(URL.createObjectURL(event.target.files[0]));
        }
    };
    const onChangeProfileImage = (event: BaseSyntheticEvent) => {
        if (event.target.files && event.target.files.length > 0) {
            setPatchReq({
                ...patchReq,
                profile_image: event.target.files[0]
            });
            setProfileImage(URL.createObjectURL(event.target.files[0]));
        }
    };

    const handleColorChange = (e: any, title: string) => {
        setBrandColor({ ...brandColor, [title]: e.hex });
    };

    const patchWorkspaceThemeInformation = async () => {
        if (!brandColor.primary_color && !brandColor.accent_color && !brandColor.text_color) return;
        const formData = new FormData();
        Object.keys(brandColor).forEach((key: any) => {
            if (!workspace.theme) {
                //@ts-ignore
                formData.append(key, brandColor[key]);
            }
            //@ts-ignore
            else if (workspace.theme[key] !== brandColor[key]) formData.append(key, brandColor[key]);
        });

        try {
            await patchTheme({ workspace_id: workspace.id, body: formData });
            router.push(router.asPath, undefined);
            toast('Theme updated!!!', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
        } catch (e) {
            toast(t(toastMessage.somethingWentWrong).toString(), { type: 'error', toastId: ToastId.ERROR_TOAST });
        }
    };

    const patchWorkspaceInformation = async () => {
        const formData = new FormData();
        Object.keys(patchReq).forEach((key: any) => {
            //@ts-ignore
            if (workspace[key] !== patchReq[key]) formData.append(key, patchReq[key]);
        });

        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
        if (response.error) {
            toast(response.error.data || t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST });
        }
        if (response.data) {
            dispatch(setWorkspace(response.data));
            toast(t(toastMessage.workspaceUpdate).toString(), { type: 'success', toastId: ToastId.SUCCESS_TOAST });
        }
    };

    const BrandThemeColors = () => (
        <>
            <SubTitleRenderer title={'Branding'} description={'Update your branding preferences'} />

            <div className="flex gap-8">
                <div className="pb-6">
                    <h1 className="text-lg">Primary</h1>
                    <div className="rounded-lg">
                        <div className="p-2 border-[1px] cursor-pointer flex flex-row items-center gap-2 border-gray-200" aria-describedby={'a'} onClick={(event: any) => setPrimaryEl(event.currentTarget)}>
                            <div style={{ backgroundColor: brandColor.primary_color }} className={`border-[1px] border-[#eaeaea] rounded-full !w-5 !h-5`} />
                            <p>{brandColor.primary_color}</p>
                        </div>
                    </div>
                    <Popover
                        open={openPrimary}
                        anchorEl={primaryEl}
                        onClose={() => setPrimaryEl(null)}
                        anchorOrigin={{
                            vertical: 'bottom',
                            horizontal: 'left'
                        }}
                    >
                        <ChromePicker color={brandColor.primary_color} onChange={(e: any) => handleColorChange(e, 'primary_color')} disableAlpha={true} />
                    </Popover>
                </div>

                <div className="pb-6">
                    <h1 className="text-lg">Accent</h1>
                    <div className="rounded-lg">
                        <div className="p-2 border-[1px] cursor-pointer flex flex-row items-center gap-2 border-gray-200" aria-describedby={'a'} onClick={(event: any) => setAccentEl(event.currentTarget)}>
                            <div style={{ backgroundColor: brandColor.accent_color }} className={`border-[1px] border-[#eaeaea] rounded-full !w-5 !h-5`} />
                            <p>{brandColor.accent_color}</p>
                        </div>
                    </div>
                    <Popover
                        open={openAccent}
                        anchorEl={accentEl}
                        onClose={() => setAccentEl(null)}
                        anchorOrigin={{
                            vertical: 'bottom',
                            horizontal: 'left'
                        }}
                    >
                        <ChromePicker color={brandColor.accent_color} onChange={(e: any) => handleColorChange(e, 'accent_color')} disableAlpha={true} />
                    </Popover>
                </div>

                <div className="pb-6">
                    <h1 className="text-lg">Text</h1>
                    <div className="rounded-lg">
                        <div className="p-2 border-[1px] cursor-pointer flex flex-row items-center gap-2 border-gray-200" aria-describedby={'a'} onClick={(event: any) => setTextEl(event.currentTarget)}>
                            <div style={{ backgroundColor: brandColor.text_color }} className={`border-[1px] border-[#eaeaea] rounded-full !w-5 !h-5`} />
                            <p>{brandColor.text_color}</p>
                        </div>
                    </div>
                    <Popover
                        open={openText}
                        anchorEl={textEl}
                        onClose={() => setTextEl(null)}
                        anchorOrigin={{
                            vertical: 'bottom',
                            horizontal: 'left'
                        }}
                    >
                        <ChromePicker color={brandColor.text_color} onChange={(e: any) => handleColorChange(e, 'text_color')} disableAlpha={true} />
                    </Popover>
                </div>
            </div>
            <Button isLoading={isLoading} className="w-full md:w-auto !rounded-xl !bg-blue-600 h-[50px] mb-10" onClick={patchWorkspaceThemeInformation}>
                Update Brand Theme
            </Button>
        </>
    );

    return (
        <>
            <SubTitleRenderer title={'Workspace Information'} description={'Update your workspace profile'} />
            <div>
                <DynamicContainer>
                    <div className=" relative">
                        <div className="product-image h-44 w-full overflow-hidden md:h-80 xl:h-[380px]">
                            <Image data-testid="banner-image-display" src={bannerImage} priority layout="fill" objectFit="cover" objectPosition="center" alt={workspace?.title} />
                        </div>
                    </div>
                    <div className="product-box relative top-0 bottom-0 pb-24">
                        <div className="product-image absolute left-10 bg-white border-[1px] border-neutral-300 pb-24 hover:border-neutral-400 rounded-full z-10 h-24 w-24 sm:h-32 sm:w-32 md:h-40 md:w-40 xl:h-40 xl:w-40 2xl:h-[180px] 2xl:w-[180px] overflow-hidden -top-12 sm:-top-16 md:-top-20 xl:-top-[88px] 2xl:-top-24">
                            <Image src={profileImage} layout="fill" objectFit="contain" alt={workspace.title} />
                        </div>
                    </div>
                </DynamicContainer>
                <div className="flex space-x-6 lg:w-2/3 pb-4">
                    <div className="flex flex-col w-full ">
                        Profile Image
                        <input
                            accept="image/png, image/jpeg"
                            placeholder="upload a profile image"
                            className="block z-10 w-full text-sm text-gray-900 border border-gray-300 rounded-md cursor-pointer bg-gray-50 file:rounded-l-md file:py-3 file:px-3 file:bg-gray-500 file:text-white file:border-none "
                            id="profile"
                            onChange={onChangeProfileImage}
                            type="file"
                            name="profile_image"
                        />
                    </div>
                    <div className="flex w-full flex-col">
                        Banner Image
                        <input
                            data-testid="workspace-banner"
                            accept="image/png, image/jpeg"
                            className="block z-10 w-full text-sm text-gray-900 border border-gray-300 rounded-md cursor-pointer bg-gray-50 file:rounded-l-md file:py-3 file:px-3 file:bg-gray-500 file:text-white file:border-none "
                            id="banner"
                            onChange={onChangeBannerImage}
                            type="file"
                            name="banner_image"
                        />
                    </div>
                </div>
            </div>
            <div className="w-full lg:w-2/3">
                <div className="pb-6">
                    <h1 className="text-lg">Workspace title</h1>
                    <div className=" flex flex-col justify-between w-full">
                        <TextField
                            data-testid="workspace-title"
                            error={false}
                            helperText=""
                            size="medium"
                            name="title"
                            placeholder="Enter your workspace title"
                            value={patchReq.title}
                            onChange={(event) => {
                                setPatchReq({
                                    ...patchReq,
                                    title: event.target.value
                                });
                            }}
                            className={`w-full`}
                        />
                    </div>
                </div>
                <div className="pb-6">
                    <h1 className="text-lg">Workspace Description</h1>
                    <textarea
                        id="workspace-description"
                        name="description"
                        value={patchReq.description}
                        onChange={(event) => {
                            setPatchReq({
                                ...patchReq,
                                description: event.target.value
                            });
                        }}
                        rows={3}
                        className=" border-solid border-gray-300 text-gray-900 sm:text-sm rounded-lg block w-full p-2.5"
                        placeholder="Enter about your workspace"
                        required
                    />
                </div>

                <Button isLoading={isLoading} type={'submit'} className="w-full md:w-auto !rounded-xl !bg-blue-600 h-[50px] mb-10" onClick={patchWorkspaceInformation}>
                    Update workspace profile
                </Button>

                {environments.ENABLE_BRAND_COLORS && <BrandThemeColors />}
            </div>
        </>
    );
}
