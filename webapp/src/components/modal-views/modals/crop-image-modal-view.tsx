import React, { useState } from 'react';

import AvatarEditor from 'react-avatar-editor';

import Button from '@app/components/ui/button';

import { useModal } from '../context';

interface ICropImageModalViewProps {
    profileEditorRef: React.LegacyRef<AvatarEditor> | undefined;
    uploadImage: string | File;
    profileInputRef: any;
    onSave: (e: any) => void;
}

export default function CropImageModalView({ profileEditorRef, uploadImage, profileInputRef, onSave }: ICropImageModalViewProps) {
    const [scale, setScale] = useState(1);
    const [isLoading, setLoading] = useState(false);
    const { closeModal } = useModal();
    return (
        <div className="p-4 bg-white flex flex-col items-center rounded-[8px]">
            <h1 className="font-bold text-lg mb-2">Update your Workspace Profile picture</h1>
            <AvatarEditor crossOrigin="anonymous" ref={profileEditorRef} image={uploadImage} width={250} height={250} border={50} borderRadius={16} color={[0, 0, 0, 0.6]} scale={scale} rotate={0} />
            <div className="flex mb-2 gap-1 text-3xl text-gray-600 justify-center items-center">
                <span>-</span>
                <input name="scale" type="range" onChange={(e) => setScale(parseFloat(e.target.value))} min={1} max={4} step="0.01" defaultValue={1} />
                <span>+</span>
            </div>
            <div className="flex justify-around w-full">
                <Button
                    data-testid="save-button"
                    isLoading={isLoading}
                    variant="solid"
                    color="info"
                    className="hover:!translate-y-0 mr-2 flex-1 !rounded shadow-none"
                    disabled={!uploadImage}
                    onClick={(e) => {
                        onSave(e);
                        setLoading(true);
                    }}
                >
                    Save Image
                </Button>
                <Button variant="solid" color="info" disabled={isLoading} className="hover:!translate-y-0 !rounded !bg-black-500 hover:!bg-black-600 flex-1 !shadow-none" onClick={closeModal}>
                    Cancel
                </Button>
            </div>
        </div>
    );
}
