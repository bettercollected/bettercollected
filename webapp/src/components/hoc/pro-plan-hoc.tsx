import React, { ReactNode } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { useModal } from '@app/components/modal-views/context';
import { useUpgradeModal } from '@app/components/modal-views/upgrade-modal-context';
import { Features } from '@app/constants/locales/feature';
import { upgradeConst } from '@app/constants/locales/upgrade';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface IProPlanHoc {
    children: ReactNode;
    hideChildrenIfPro?: boolean;
    feature?: Features;
}

export default function ProPlanHoc({ children, hideChildrenIfPro = false, feature = Features.default }: IProPlanHoc) {
    const isProPlan = useAppSelector(selectIsProPlan);
    const { openModal } = useUpgradeModal();
    const { t } = useTranslation();
    const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
        event.stopPropagation();
        event.preventDefault();
        if (!isProPlan) {
            // router.push(`/${workspace.workspaceName}/upgrade`);
            // @ts-ignore
            openModal({ featureText: t(upgradeConst.features[feature.toString()].slogan) });
        }
    };

    return !isProPlan || !hideChildrenIfPro ? <div onClick={(event) => handleClick(event)}>{children}</div> : <></>;
}
