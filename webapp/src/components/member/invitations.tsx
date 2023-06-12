import { useTranslation } from 'next-i18next';

import InvitationsTable from '@app/components/settings/invitations-table';
import Loader from '@app/components/ui/loader';
import { members } from '@app/constants/locales/members';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersInvitationsQuery } from '@app/store/workspaces/members-n-invitations-api';

export default function Invitations() {
    const workspace = useAppSelector((state) => state.workspace);
    const { t } = useTranslation();
    const { data, isLoading } = useGetWorkspaceMembersInvitationsQuery({ workspaceId: workspace.id });
    if (isLoading) {
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    }
    return (
        <>
            <p className="body1 ">
                {t(members.pendingRequests.default)} ({data?.items.length})
            </p>
            <p className="body4 mt-4 mb-6 text-black-700">{t(members.pendingRequests.description)}</p>
            <InvitationsTable data={data} />
        </>
    );
}
