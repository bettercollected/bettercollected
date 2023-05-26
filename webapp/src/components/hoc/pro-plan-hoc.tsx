import React, { ReactNode } from 'react';

import { useRouter } from 'next/router';

import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface IProPlanHoc {
    children: ReactNode;
    hideChildrenIfPro?: boolean;
}

export default function ProPlanHoc({ children, hideChildrenIfPro = false }: IProPlanHoc) {
    const isProPlan = useAppSelector(selectIsProPlan);
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
        if (!isProPlan) {
            event.stopPropagation();
            event.preventDefault();
            router.push(`/${workspace.workspaceName}/upgrade`);
        }
    };

    return !isProPlan || !hideChildrenIfPro ? <div onClick={(event) => handleClick(event)}>{children}</div> : <></>;
}
