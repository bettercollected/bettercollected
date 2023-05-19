import DashboardLayout from '@app/components/sidebar/dashboard-layout';

export default function Responders() {
    return <DashboardLayout></DashboardLayout>;
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
