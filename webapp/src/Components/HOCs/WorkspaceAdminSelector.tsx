import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

interface IWorkspaceAdminSelectorProps {
    children: React.ReactNode | React.ReactNode[];
}

export default function WorkspaceAdminSelector({ children }: IWorkspaceAdminSelectorProps) {
    const isAdmin = useAppSelector(selectIsAdmin);

    if (isAdmin) return <>{children}</>;
    return null;
}