import React from 'react';

import { TextField } from '@mui/material';

import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { useAppSelector } from '@app/store/hooks';

export function WorkspaceDangerZoneSettings() {
    const workspace = useAppSelector((state) => state.workspace);

    const { openModal } = useModal();
    return (
        <div className="lg:w-2/3 mb-10">
            <h1 className="text-xl pb-2 font-bold">Danger Zone</h1>
            <div className="border border-red-200 rounded">
                <div className=" flex p-4 items-center space-between">
                    <div className="flex flex-col items-start w-full">
                        <h1 className=" w-full md:w-2/3 font-medium">{workspace.customDomain ? 'Update your custom domain' : 'Setup your custom Domain'}</h1>
                        <div className="w-full text-sm text-gray-600">
                            {workspace.customDomain ? (
                                <>
                                    Your Custom Domain is currently set to <span className="font-bold"> {workspace.customDomain}.</span>
                                </>
                            ) : (
                                'You have not set up custom domain.'
                            )}
                        </div>
                    </div>
                    <Button
                        isLoading={false}
                        className=" !bg-gray-100 !px-8 !py-1 hover:text-white !font-normal hover:!bg-red-800 text-red-800 rounded border !border-gray-300"
                        onClick={() => {
                            openModal('UPDATE_WORKSPACE_DOMAIN');
                        }}
                    >
                        Update
                    </Button>
                </div>

                <div className="h-[1px] bg-gray-200" />

                <div className="flex space-between items-center w-full p-4">
                    <div className="flex items-start flex-col w-full">
                        <h1 className="w-full md:w-2/3 font-medium">Update Your Workspace Handle</h1>
                        <div className="w-full text-sm text-gray-600">
                            Your workspace handle is currently set to <span className="font-bold"> {workspace.workspaceName}.</span>
                        </div>
                    </div>
                    <Button
                        isLoading={false}
                        className=" !bg-gray-100 !h-auto !px-8 !py-3 hover:text-white !font-normal hover:!bg-red-800 text-red-800 rounded border !border-gray-300"
                        onClick={() => {
                            openModal('UPDATE_WORKSPACE_HANDLE');
                        }}
                    >
                        Update
                    </Button>
                </div>
            </div>
        </div>
    );
}
