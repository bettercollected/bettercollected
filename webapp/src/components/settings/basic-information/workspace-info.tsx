import { ChangeEvent, FormEvent, useState } from 'react';

import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';

import BetterInput from '@app/components/common/input';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { ToastId } from '@app/constants/toastId';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function WorkspaceInfo({ workspace }: any) {
    const dispatch = useAppDispatch();

    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

    const [workspaceInfo, setWorkspaceInfo] = useState({
        title: workspace.title || '',
        description: workspace.description || ''
    });

    const onChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        if (e.target.name === 'title') {
            setWorkspaceInfo({ ...workspaceInfo, title: e.target.value });
        } else if (e.target.name === 'description') {
            setWorkspaceInfo({ ...workspaceInfo, description: e.target.value });
        }
    };

    const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        const formData = new FormData();
        Object.keys(workspaceInfo).forEach((key: any) => {
            //@ts-ignore
            if (workspace[key] !== workspaceInfo[key]) formData.append(key, workspaceInfo[key]);
        });
        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });

        if (response.error) {
            toast('Something went wrong!!!', { toastId: ToastId.ERROR_TOAST });
        }
        if (response.data) {
            dispatch(setWorkspace(response.data));
            toast('Workspace Updated!!!', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
        }
    };

    return (
        <SettingsCard>
            <form onSubmit={onSubmit}>
                <div>
                    <div className="body1">Workspace Title</div>
                    <BetterInput onChange={onChange} value={workspaceInfo.title} name="title" placeholder="Enter your workspace title" />
                </div>
                <div>
                    <div className="body1">Workspace Description</div>
                    <BetterInput className="w-full" size="medium" rows={5} multiline onChange={onChange} value={workspaceInfo.description} name="description" placeholder="Enter your workspace description" />
                </div>
                <div>
                    <Button type="submit" disabled={isLoading || !workspaceInfo.title}>
                        Save
                    </Button>
                </div>
            </form>
        </SettingsCard>
    );
}
