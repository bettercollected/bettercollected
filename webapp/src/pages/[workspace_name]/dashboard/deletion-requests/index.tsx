import DashboardLayout from '@app/components/sidebar/dashboard-layout';

export default function DeletionRequests() {
    return <DashboardLayout></DashboardLayout>;
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
