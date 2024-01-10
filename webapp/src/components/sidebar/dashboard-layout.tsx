import ChatwootWidget from '@Components/Common/ChatwootWidget';

import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import environments from '@app/configs/environments';

export default function DashboardLayout({ children, boxClassName = 'p-5 lg:p-10', dashboardContentClassName = '' }: any) {
    return (
        <SidebarLayout boxClassName={boxClassName}>
            {environments.CHATWOOT_ENABLE && <ChatwootWidget />}
            <div className={`${dashboardContentClassName}`}>{children}</div>
        </SidebarLayout>
    );
}
