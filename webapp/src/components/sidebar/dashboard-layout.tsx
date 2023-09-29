import SidebarLayout from '@app/components/sidebar/sidebar-layout';

export default function DashboardLayout({
                                            children,
                                            boxClassName = 'p-5 lg:p-10',
                                            dashboardContentClassName = ''
                                        }: any) {
    return (
        <SidebarLayout boxClassName={boxClassName}>
            <div className={`${dashboardContentClassName}`}>{children}</div>
        </SidebarLayout>
    );
}
