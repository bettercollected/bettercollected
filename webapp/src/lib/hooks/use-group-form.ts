import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { setForm } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';
import { useAddFormOnGroupMutation, useDeleteGroupFormMutation } from '@app/store/workspaces/api';

interface IDeleteFormFromGroupProps {
    group: ResponderGroupDto | null;
    workspaceId: string;
    form: StandardFormDto;
}

interface IAddFormOnGroupProps {
    groups: Array<ResponderGroupDto>;
    groupsForUpdate: Array<ResponderGroupDto | null> | null;
    workspaceId: string;
    form: StandardFormDto;
}

export function useGroupForm() {
    const [addForm] = useAddFormOnGroupMutation();
    const [removeForm] = useDeleteGroupFormMutation();
    const dispatch = useAppDispatch();
    const router = useRouter();
    const { closeModal } = useModal();
    const fullScreenModal = useFullScreenModal();
    const { t } = useTranslation();
    const deleteFormFromGroup = async ({ group, workspaceId, form }: IDeleteFormFromGroupProps) => {
        try {
            await removeForm({
                workspaceId: workspaceId,
                groupId: group?.id,
                formId: form.formId
            }).unwrap();
            dispatch(setForm({ ...form, groups: form.groups?.filter((formGroup) => formGroup.id !== group?.id) }));

            toast(t(toastMessage.removed).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            closeModal();
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };

    const addFormOnGroup = async ({ groups, groupsForUpdate, workspaceId, form }: IAddFormOnGroupProps) => {
        try {
            let groupIds = [];
            if (groupsForUpdate) {
                for (let group of groupsForUpdate) {
                    groupIds.push(group?.id);
                }
            }
            await addForm({
                workspaceId: workspaceId,
                groups: groupIds,
                formId: form.formId
            });
            //     .then((data: any) => {
            //     const dataArray = Array.from(data);
            //     dispatch(setForm({ ...form, groups: [...groups, ...dataArray] }));
            // });
            router.push(router.asPath);
            toast(t(toastMessage.addedOnGroup).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            // closeModal();
            // fullScreenModal.closeModal();
        } catch (error) {
            console.log(error);
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    return {
        deleteFormFromGroup,
        addFormOnGroup
    };
}
