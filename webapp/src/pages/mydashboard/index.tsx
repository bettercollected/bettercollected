import { useDrawer } from '@app/components/drawer-views/context';
import AuthHoc from '@app/components/hoc/auth-hoc';
import Hamburger from '@app/components/ui/hamburger';

export default function CreatorDashboard() {
    const { openDrawer, isOpen, closeDrawer } = useDrawer();
    return (
        // <AuthHoc>
        <div className="p-4">
            <div className="flex justify-end">
                <Hamburger isOpen={isOpen} onClick={() => openDrawer('DASHBOARD_SIDEBAR')} />
            </div>
        </div>
        // </AuthHoc>
    );
}
