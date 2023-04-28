import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceMemberMutation } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getFullNameFromUser } from '@app/utils/userUtils';

export default function DeleteMemberModal({ member }: any) {
    const { closeModal } = useModal();
    const workspace = useAppSelector(selectWorkspace);
    const [trigger] = useDeleteWorkspaceMemberMutation();

    const handleDelete = () => {
        const response: any = trigger({ workspaceId: workspace.id, userId: member.id });
        if (response.data) {
            toast('Member removed from workspace', { type: 'success' });
        }
        if (response.error) {
            toast('Failed to remove user', { type: 'error' });
        }
        closeModal();
    };

    return (
        <div className="rounded p-10 bg-white items-center w-full max-w-[465px] flex flex-col relative">
            <Close
                className="absolute top-5 right-5"
                onClick={() => {
                    closeModal();
                }}
            />
            <div className="sh3 mb-5">Remove {getFullNameFromUser(member)}?</div>
            <div className="body4 text-black-600 text-center mb-10">Removing a member will also remove all forms imported by the user</div>
            <div className="flex w-full gap-4 justify-end">
                <Button variant="solid" color="gray" size="medium" className="!bg-black-500" onClick={() => closeModal()}>
                    Cancel
                </Button>
                <Button data-testid="logout-button" variant="solid" size="medium" color="danger" onClick={handleDelete}>
                    Delete
                </Button>
            </div>
        </div>
    );
}
