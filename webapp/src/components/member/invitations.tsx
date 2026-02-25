import { useTranslation } from 'next-i18next';

import InvitationsTable from '@app/Components/settings/invitations-table';
import Loader from '@app/Components/ui/loader';
import { members } from '@app/constants/locales/members';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersInvitationsQuery } from '@app/store/workspaces/members-n-invitations-api';

export default function Invitations() {
    const workspace = useAppSelector((state) => state.workspace);
    const { t } = useTranslation();
    const { data, isLoading } = useGetWorkspaceMembersInvitationsQuery({ workspaceId: workspace.id });
    if (isLoading) {
        return (
            <div className=" flex w-full justify-center py-10">
                <Loader />
            </div>
        );
    }
    if (data)
        return (
            <>
                <p className="body1 ">
                    {t(members.pendingRequests.default)} ({data.items.length})
                </p>
                <p className="body4 text-black-700 mb-6 mt-4">{t(members.pendingRequests.description)}</p>

                <InvitationsTable data={data} />
            </>
        );
    return <></>;
}
