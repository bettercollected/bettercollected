import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

export default function WorkspaceAdminHoc({ children }: any) {
    const isAdmin = useAppSelector(selectIsAdmin);

    return <>{isAdmin && children}</>;
}
