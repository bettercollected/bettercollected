import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';

import UserMore from '@app/components/icons/user-more';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { groupConstant } from '@app/constants/locales/group';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function EmptyGroup({ formId }: { formId?: string }) {
    const { t } = useTranslation();
    const isAdmin = useAppSelector(selectIsAdmin);
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    return (
        <div className="my-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body2 text-center !font-medium sm:w-[252px] mt-7 mb-6">{t(groupConstant.title)}</p>
            <Tooltip title={!isAdmin ? t(toolTipConstant.noAccessToGroup) : ''}>
                <Button
                    disabled={!isAdmin}
                    size="small"
                    onClick={() =>
                        router.push({
                            pathname: `/${workspace.workspaceName}/dashboard/responders-groups/create-group`,
                            query: formId ? { formId } : {}
                        })
                    }
                >
                    {t(groupConstant.createNewGroup.default)}
                </Button>
            </Tooltip>
        </div>
    );
}
