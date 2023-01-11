import React, { BaseSyntheticEvent, useState } from 'react';

import { Popover, TextField } from '@mui/material';
import { ChromePicker } from 'react-color';
import { toast } from 'react-toastify';

import Button from '@app/components/ui/button';
import Image from '@app/components/ui/image';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

const SubTitleRenderer = ({ title, description }: any) => {
    return (
        <div className={` pb-4 border-b-gray-200 mt-6 mb-4 border-b-[1px] w-2/3 `}>
            <h1 className="text-2xl font-bold text-black">{title}</h1>
            {!!description && <p className="text-gray-600">{description}</p>}
        </div>
    );
};

export function WorkspaceInformationSettings() {
    const dispatch = useAppDispatch();
    const workspace = useAppSelector((state) => state.workspace);
    const [patchReq, setPatchReq] = useState<any>({
        title: workspace.title,
        description: workspace.description
    });
    const [bannerImage, setBannerImage] = useState(workspace.bannerImage);
    const [profileImage, setProfileImage] = useState(workspace.profileImage);

    const [brandColor, setBrandColor] = useState({ primary_color: '#fff', tertiary_color: '#fff', text_color: '#fff' });

    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

    const [anchorEl, setAnchorEl] = React.useState<HTMLButtonElement | null>(null);
    const open = Boolean(anchorEl);
    const id = open ? 'simple-popover' : undefined;

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
        // setPrimaryColor(e.hex);
        setBrandColor({ ...brandColor, [title]: e.hex });
    };

    const patchWorkspaceInformation = async () => {
        const formData = new FormData();
        Object.keys(patchReq).forEach((key) => {
            // @ts-ignore
            if (workspace[key] !== patchReq[key]) formData.append(key, patchReq[key]);
        });

        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
        if (response.error) {
            toast('Something went wrong!!!');
        }
        if (response.data) {
            dispatch(setWorkspace(response.data));
            toast('Workspace Updated!!!', { type: 'success' });
        }
    };

    return (
        <>
            <SubTitleRenderer title={'Workspace Information'} description={'Update your workspace profile'} />
            <div>
                <div className=" relative">
                    <div className="product-image h-44 w-full overflow-hidden md:h-80 xl:h-[380px]">
                        <Image src={bannerImage || ''} priority layout="fill" objectFit="contain" objectPosition="center" alt={workspace?.title} />
                    </div>
                </div>
                <div className="product-box relative top-0 bottom-0 pb-24">
                    <div className="product-image absolute bg-white border-[1px] border-neutral-300 pb-24 hover:border-neutral-400 rounded-full z-10 h-24 w-24 sm:h-32 sm:w-32 md:h-40 md:w-40 xl:h-40 xl:w-40 2xl:h-[180px] 2xl:w-[180px] overflow-hidden -top-12 sm:-top-16 md:-top-20 xl:-top-[88px] 2xl:-top-24">
                        <Image src={profileImage || ''} layout="fill" objectFit="contain" alt={workspace.title} />
                    </div>
                </div>
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

                <SubTitleRenderer title={'Branding'} description={'Update your branding preferences'} />
                <div className="pb-6">
                    <h1 className="text-lg">Brand Primary</h1>
                    <div className="rounded-lg">
                        <div className="p-2 border-[1px] cursor-pointer flex flex-row items-center gap-2 border-gray-200" aria-describedby={'a'} onClick={(event: any) => setAnchorEl(event.currentTarget)}>
                            <div style={{ backgroundColor: brandColor.primary_color }} className={`border-[1px] border-[#eaeaea] rounded-full !w-5 !h-5`} />
                            <p>{brandColor.primary_color}</p>
                        </div>
                    </div>
                    <Popover
                        id={id}
                        open={open}
                        anchorEl={anchorEl}
                        onClose={() => setAnchorEl(null)}
                        anchorOrigin={{
                            vertical: 'bottom',
                            horizontal: 'left'
                        }}
                    >
                        <ChromePicker color={brandColor.primary_color} onChange={(e: any) => handleColorChange(e, 'primary_color')} disableAlpha={true} />
                    </Popover>
                </div>

                <div className="pb-6">
                    <h1 className="text-lg">Brand Accent</h1>
                    <div className="rounded-lg">
                        <div className="p-2 border-[1px] cursor-pointer flex flex-row items-center gap-2 border-gray-200" aria-describedby={'a'} onClick={(event: any) => setAnchorEl(event.currentTarget)}>
                            <div style={{ backgroundColor: brandColor.tertiary_color }} className={`border-[1px] border-[#eaeaea] rounded-full !w-5 !h-5`} />
                            <p>{brandColor.tertiary_color}</p>
                        </div>
                    </div>
                    <Popover
                        id={id}
                        open={open}
                        anchorEl={anchorEl}
                        onClose={() => setAnchorEl(null)}
                        anchorOrigin={{
                            vertical: 'bottom',
                            horizontal: 'left'
                        }}
                    >
                        <ChromePicker color={brandColor.tertiary_color} onChange={(e: any) => handleColorChange(e, 'tertiary_color')} disableAlpha={true} />
                    </Popover>
                </div>

                <div className="pb-6">
                    <h1 className="text-lg">Brand Accent</h1>
                    <div className="rounded-lg">
                        <div className="p-2 border-[1px] cursor-pointer flex flex-row items-center gap-2 border-gray-200" aria-describedby={'a'} onClick={(event: any) => setAnchorEl(event.currentTarget)}>
                            <div style={{ backgroundColor: brandColor.text_color }} className={`border-[1px] border-[#eaeaea] rounded-full !w-5 !h-5`} />
                            <p>{brandColor.text_color}</p>
                        </div>
                    </div>
                    <Popover
                        id={id}
                        open={open}
                        anchorEl={anchorEl}
                        onClose={() => setAnchorEl(null)}
                        anchorOrigin={{
                            vertical: 'bottom',
                            horizontal: 'left'
                        }}
                    >
                        <ChromePicker color={brandColor.text_color} onChange={(e: any) => handleColorChange(e, 'text_color')} disableAlpha={true} />
                    </Popover>
                </div>

                <Button isLoading={isLoading} type={'submit'} className="w-full md:w-auto !rounded-xl !bg-blue-600 h-[50px] mb-10" onClick={patchWorkspaceInformation}>
                    Update workspace profile
                </Button>
            </div>
        </>
    );
}
