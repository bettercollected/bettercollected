import SidebarLayout from '@app/components/sidebar/sidebar-layout';

export default function DashboardLayout({ children, sidebarClassName = '', dashboardContentClassName = '' }: any) {
    return (
        <SidebarLayout boxClassName={sidebarClassName}>
            <div className={`py-6 ${dashboardContentClassName}`}>{children}</div>
        </SidebarLayout>
    );
}
