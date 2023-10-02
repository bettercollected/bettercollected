import React, {useState} from 'react';

import {useTranslation} from 'next-i18next';
import {NextSeo} from 'next-seo';
import {useRouter} from 'next/router';
import {toast} from 'react-toastify';

import RegexCard from '@app/components/cards/regex-card';
import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import GroupInfo from '@app/components/group/group-info';
import GroupMember from '@app/components/group/group-member';
import Back from '@app/components/icons/back';
import {useModal} from '@app/components/modal-views/context';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import {buttonConstant} from '@app/constants/locales/button';
import {localesCommon} from '@app/constants/locales/common';
import {groupConstant} from '@app/constants/locales/group';
import {members} from '@app/constants/locales/members';
import {toastMessage} from '@app/constants/locales/toast-message';
import {ToastId} from '@app/constants/toastId';
import {GroupInfoDto} from '@app/models/dtos/groups';
import {WorkspaceDto} from '@app/models/dtos/workspaceDto';
import {handleRegexType} from '@app/models/enums/groupRegex';
import {BreadcrumbsItem} from '@app/models/props/breadcrumbs-item';
import {useAppSelector} from '@app/store/hooks';
import {useCreateRespondersGroupMutation} from '@app/store/workspaces/api';
import {selectWorkspace} from '@app/store/workspaces/slice';
import AppButton from "@Components/Common/Input/Button/AppButton";

export default function CreateGroup() {
    const router = useRouter();
    let formId: string = (router?.query?.formId as string) ?? '';
    const locale = router?.locale === 'en' ? '' : `${router?.locale}/`;
    const {t} = useTranslation();
    const {closeModal} = useModal();
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const [groupInfo, setGroupInfo] = useState<GroupInfoDto>({
        name: '',
        description: '',
        emails: [],
        regex: '',
        formId: formId ?? ''
    });
    const [createResponderGroup, {isLoading}] = useCreateRespondersGroupMutation();
    const handleInput = (event: any) => {
        setGroupInfo({
            ...groupInfo,
            [event.target.id]: event.target.value
        });
    };

    const handleRegex = (regex: string, type: handleRegexType) => {
        if (type === handleRegexType.ADD) {
            setGroupInfo({
                ...groupInfo,
                regex
            });
            closeModal();
        } else if (type === handleRegexType.REMOVE) {
            setGroupInfo({
                ...groupInfo,
                regex: ''
            });
        }
    };

    const handleCreateGroup = async () => {
        try {
            await createResponderGroup({
                groupInfo: groupInfo,
                workspace_id: workspace.id
            }).then((response) => {
                if ('data' in response) {
                    toast(t(toastMessage.workspaceSuccess).toString(), {
                        toastId: ToastId.SUCCESS_TOAST,
                        type: 'success'
                    });
                    router.push(`/${workspace?.workspaceName}/dashboard/responders-groups?view=Groups`);
                } else toast(t(toastMessage.somethingWentWrong).toString(), {
                    toastId: ToastId.ERROR_TOAST,
                    type: 'error'
                });
            });
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), {toastId: ToastId.ERROR_TOAST, type: 'error'});
        }
    };

    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: t(localesCommon.respondersAndGroups),
            url: `/${locale}${workspace?.workspaceName}/dashboard/responders-groups`
        },
        {
            title: t(groupConstant.groups),
            url: `/${locale}${workspace?.workspaceName}/dashboard/responders-groups?view=Groups`
        },
        {
            title: t(groupConstant.createGroup),
            disabled: true
        }
    ];

    const handleAddMembers = (members: Array<string>) => {
        if (groupInfo.emails) {
            setGroupInfo({
                ...groupInfo,
                emails: [...groupInfo.emails, ...members]
            });
            closeModal();
        } else {
            toast(t(toastMessage.somethingWentWrong).toString(), {toastId: ToastId.ERROR_TOAST, type: 'error'});
        }
    };

    const handleRemoveMember = (email: string) => {
        setGroupInfo({
            ...groupInfo,
            emails: groupInfo.emails?.filter((groupInfoEmail) => groupInfoEmail !== email)
        });
    };
    return (
        <DashboardLayout>
            <NextSeo title={t(groupConstant.createGroup) + ' | ' + workspace.workspaceName} noindex={true}
                     nofollow={true}/>
            <div className="flex flex-col  -mt-6 md:max-w-[700px] xl:max-w-[1000px]">
                <BreadcrumbsRenderer items={breadcrumbsItem}/>
                <div className="md:max-w-[618px]">
                    <div className="flex flex-col gap-10">
                        <div className="flex justify-between">
                            <div className="flex gap-2  items-center">
                                <Back onClick={() => router.back()} className="cursor-pointer"/>
                                <p className="h4">{t(groupConstant.createGroup)}</p>
                            </div>
                            <AppButton isLoading={isLoading}
                                       disabled={!groupInfo.name || (groupInfo.emails?.length === 0 && groupInfo.regex?.length === 0)}
                                       onClick={handleCreateGroup}>
                                {t(buttonConstant.saveGroup)}
                            </AppButton>
                        </div>

                        <GroupInfo handleInput={handleInput} groupInfo={groupInfo}/>
                        <div>
                            <p className="leading-none mb-6 body1">{t(members.default)}</p>
                            <RegexCard handleRegex={handleRegex} regex={groupInfo.regex}/>
                            {groupInfo.emails &&
                                <GroupMember emails={groupInfo.emails} handleAddMembers={handleAddMembers}
                                             handleRemoveMember={handleRemoveMember}/>}
                        </div>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
}
export {getAuthUserPropsWithWorkspace as getServerSideProps} from '@app/lib/serverSideProps';
