import React, { ReactNode } from 'react';

import { useRouter } from 'next/router';

import { useModal } from '@app/components/modal-views/context';
import { useUpgradeModal } from '@app/components/modal-views/upgrade-modal-context';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface IProPlanHoc {
    children: ReactNode;
    hideChildrenIfPro?: boolean;
}

export default function ProPlanHoc({ children, hideChildrenIfPro = false }: IProPlanHoc) {
    const isProPlan = useAppSelector(selectIsProPlan);
    const { openModal } = useUpgradeModal();
    const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
        if (!isProPlan) {
            event.stopPropagation();
            event.preventDefault();
            // router.push(`/${workspace.workspaceName}/upgrade`);
            openModal('UPGRADE_TO_PRO');
        }
    };

    return !isProPlan || !hideChildrenIfPro ? <div onClick={(event) => handleClick(event)}>{children}</div> : <></>;
}
