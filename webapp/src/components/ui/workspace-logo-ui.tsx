import React from 'react';

import AuthAccountProfileImage from '../auth/account-profile-image';
import Button from './button';

interface IWorkspaceLogoProps {
    workspaceLogoRef: any;
    onChange: (e: any) => void;
    onClick: () => void;
    image?: string;
    profileName: string;
}
export default function WorkSpaceLogoUi({ workspaceLogoRef, onChange, onClick, image, profileName }: IWorkspaceLogoProps) {
    return (
        <div className="flex md:flex-row flex-col gap-4 items-center">
            <AuthAccountProfileImage image={image} name={profileName} size={143} typography="h1" />
            <div className="flex flex-col justify-center md:items-start items-center">
                <p className="body3 mb-5 !text-black-700 md:text-start text-center">Make sure your image is less than 100MB</p>
                <input data-testid="file-upload-profile" type="file" accept="image/*" className="hidden" ref={workspaceLogoRef} onChange={onChange} />
                <Button size="small" variant="ghost" className="!text-brand-500 hover:!bg-brand-200 !bg-white !border-brand-300" onClick={onClick}>
                    Upload
                </Button>
            </div>
        </div>
    );
}
