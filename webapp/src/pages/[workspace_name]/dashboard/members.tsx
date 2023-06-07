import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';

import ProPlanHoc from '@app/components/hoc/pro-plan-hoc';
import { useModal } from '@app/components/modal-views/context';
import InvitationsTable from '@app/components/settings/invitations-table';
import MembersTable from '@app/components/settings/members-table';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/button';
import { Features } from '@app/constants/locales/feature';
import { members } from '@app/constants/locales/members';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

export default function ManageMembers({ workspace }: any) {
    const isProPlan = useAppSelector(selectIsProPlan);
    const { openModal } = useModal();
    const { t } = useTranslation();
    return (
        <DashboardLayout>
            <div className="flex justify-between">
                <div className="h4">{t(members.default)}</div>
                <ProPlanHoc hideChildrenIfPro={false} feature={Features.collaborator}>
                    <Button
                        onClick={() => {
                            if (isProPlan) openModal('INVITE_MEMBER');
                        }}
                    >
                        {t(buttonConstant.inviteCollaborator)}
                    </Button>
                </ProPlanHoc>
            </div>
            <Divider className="mt-5" />

            <MembersTable />
            {isProPlan && (
                <>
                    <div className="h4 mt-10">{t(members.invitations)}</div>
                    <Divider className="my-5" />
                    <InvitationsTable />
                </>
            )}
        </DashboardLayout>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
