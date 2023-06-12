import React, { ReactNode } from 'react';

import { useTranslation } from 'next-i18next';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { Features } from '@app/constants/locales/feature';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

interface IProPlanHoc {
    children: ReactNode;
    hideChildrenIfPro?: boolean;
    feature?: Features;
}

export default function ProPlanHoc({ children, hideChildrenIfPro = false, feature = Features.default }: IProPlanHoc) {
    const isProPlan = useAppSelector(selectIsProPlan);
    const { openModal } = useFullScreenModal();
    const { t } = useTranslation();
    const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
        event.stopPropagation();
        event.preventDefault();
        if (!isProPlan) {
            // router.push(`/${workspace.workspaceName}/upgrade`);
            openModal('UPGRADE_TO_PRO');
        }
    };

    return !isProPlan || !hideChildrenIfPro ? <div onClick={(event) => handleClick(event)}>{children}</div> : <></>;
}
