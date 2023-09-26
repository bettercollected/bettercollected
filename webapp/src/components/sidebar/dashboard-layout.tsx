import SidebarLayout from '@app/components/sidebar/sidebar-layout';

export default function DashboardLayout({ children, boxClassName = '', dashboardContentClassName = '' }: any) {
    return (
        <SidebarLayout boxClassName={boxClassName}>
            <div className={`${dashboardContentClassName}`}>{children}</div>
        </SidebarLayout>
    );
}
