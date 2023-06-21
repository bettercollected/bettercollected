import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { Typography } from '@mui/material';
import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import RegexCard from '@app/components/cards/regex-card';
import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import Back from '@app/components/icons/back';
import { Plus } from '@app/components/icons/plus';
import { useModal } from '@app/components/modal-views/context';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import Button from '@app/components/ui/button/button';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { members } from '@app/constants/locales/members';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { GroupInfoDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { useAppSelector } from '@app/store/hooks';
import { useCreateRespondersGroupMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function CreateGroup() {
    const router = useRouter();
    const locale = router?.locale === 'en' ? '' : `${router?.locale}/`;
    const { t } = useTranslation();
    const { openModal } = useModal();
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const [groupInfo, setGroupInfo] = useState<GroupInfoDto>({
        name: '',
        description: '',
        email: '',
        emails: []
    });
    const [createResponderGroup, { isLoading }] = useCreateRespondersGroupMutation();
    const handleInput = (event: any) => {
        setGroupInfo({
            ...groupInfo,
            [event.target.id]: event.target.value
        });
    };
    const handleCreateGroup = async () => {
        try {
            await createResponderGroup({
                groupInfo: groupInfo,
                workspace_id: workspace.id
            }).then((response) => {
                if ('data' in response) {
                    toast(t(toastMessage.workspaceSuccess).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
                    router.push(`/${workspace?.workspaceName}/dashboard/responders?view=Groups`);
                } else toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
            });
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };

    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: t(localesCommon.respondersAndGroups),
            url: `/${locale}${workspace?.workspaceName}/dashboard/responders`
        },
        {
            title: t(groupConstant.groups),
            url: `/${locale}${workspace?.workspaceName}/dashboard/responders?view=Groups`
        },
        {
            title: t(groupConstant.createGroup),
            disabled: true
        }
    ];
    return (
        <DashboardLayout>
            <div className="flex flex-col relative -mt-6 md:max-w-[700px] xl:max-w-[1000px]">
                <div className="absolute top-10 right-0">
                    <Button isLoading={isLoading} onClick={handleCreateGroup}>
                        {t(buttonConstant.save)}
                    </Button>
                </div>
                <div className="md:max-w-[618px]">
                    <BreadcrumbsRenderer items={breadcrumbsItem} />
                    <div className="flex gap-2 items-center">
                        <Back onClick={() => router.back()} />
                        <p className="sh1">{t(groupConstant.createGroup)}</p>
                    </div>

                    <p className="mt-11 body1">Group Basic Information</p>
                    <p className="body4 mt-[27px] leading-none mb-2">
                        {t(groupConstant.name)}
                        <span className="text-red-800">*</span>
                    </p>
                    <BetterInput value={groupInfo.name} className="!mb-0 bg-white" inputProps={{ className: '!py-3' }} id="name" placeholder={t(placeHolder.groupName)} onChange={handleInput} />
                    <p className="body4 leading-none mt-6 mb-2">{t(localesCommon.description)}</p>
                    <BetterInput value={groupInfo.description} className="!mb-0 bg-white" inputProps={{ maxLength: 250 }} id="description" placeholder={t(placeHolder.description)} rows={3} multiline onChange={handleInput} />
                    <p className="mt-10  leading-none mb-6 body1">{t(members.default)}</p>
                    <RegexCard addRegex={() => {}} />
                    <div className="flex items-center justify-between">
                        <div className="flex flex-col">
                            <p className="mt-10 leading-none mb-2 body1">Members Added ({groupInfo.emails.length})</p>
                            <p className="text-black-700 leading-none body4">{t(groupConstant.members.description)} </p>
                        </div>
                        <div onClick={() => openModal('ADD_MEMBER')} className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                            <Plus className="h-4 w-4" />
                            <Typography className="!text-brand-500  body6">Add Member</Typography>
                        </div>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
}
export { getGlobalServerSidePropsByWorkspaceName as getServerSideProps } from '@app/lib/serverSideProps';
