import { useTranslation } from 'next-i18next';

import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { setForm } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';
import { useAddFormOnGroupMutation, useDeleteGroupFormMutation } from '@app/store/workspaces/api';

interface IDeleteFormFromGroupProps {
    group: ResponderGroupDto;
    workspaceId: string;
    form: StandardFormDto;
}
interface IAddFormOnGroupProps extends IDeleteFormFromGroupProps {
    groups: any;
}
export function useGroupForm() {
    const [addForm] = useAddFormOnGroupMutation();
    const [removeForm] = useDeleteGroupFormMutation();
    const dispatch = useAppDispatch();
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const deleteFormFromGroup = async ({ group, workspaceId, form }: IDeleteFormFromGroupProps) => {
        try {
            await removeForm({
                workspaceId: workspaceId,
                groupId: group.id,
                formId: form.formId
            }).unwrap();

            dispatch(setForm({ ...form, groups: form.groups?.filter((formGroup) => formGroup.id !== group.id) }));

            toast(t(toastMessage.removed).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            closeModal();
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };

    const addFormOnGroup = async ({ groups, group, workspaceId, form }: IAddFormOnGroupProps) => {
        try {
            await addForm({
                workspaceId: workspaceId,
                groupId: group.id,
                formId: form.formId
            }).unwrap();

            dispatch(setForm({ ...form, groups: [...groups, group] }));

            toast(t(toastMessage.addedOnGroup).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            closeModal();
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    return {
        deleteFormFromGroup,
        addFormOnGroup
    };
}
