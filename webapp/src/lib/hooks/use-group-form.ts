import { useTranslation } from 'react-i18next';

import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useAddFormOnGroupMutation, useDeleteGroupFormMutation } from '@app/store/workspaces/api';
import { formGroupsAfterSave } from '@app/utils/form-groups';


interface IDeleteFormFromGroupProps {
    group: ResponderGroupDto | null;
    workspaceId: string;
    form: StandardFormDto;
}

interface IAddFormOnGroupProps {
    /** Unused; kept so existing callers compile. */
    groups?: Array<ResponderGroupDto>;
    /** The COMPLETE set of groups the form should be in (the server replaces the set). */
    groupsForUpdate: Array<ResponderGroupDto | null> | null;
    workspaceId: string;
    form: StandardFormDto;
}

export function useGroupForm() {
    const { toast } = useToast();
    const [addForm] = useAddFormOnGroupMutation();
    const [removeForm] = useDeleteGroupFormMutation();
    const dispatch = useAppDispatch();
    // the form open on the page; only it may be updated in the store (the group
    // pages work on other forms)
    const openForm = useAppSelector(selectForm);
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
            if (openForm?.formId === form.formId) {
                dispatch(setForm({ ...openForm, groups: (openForm.groups ?? []).filter((formGroup) => formGroup.id !== group?.id) }));
            }

            toast({ description: t(toastMessage.removed).toString() });
            closeModal();
        } catch (error) {
            toast({ description: t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
        }
    };

    const addFormOnGroup = async ({ groupsForUpdate, workspaceId, form }: IAddFormOnGroupProps) => {
        const groups = formGroupsAfterSave(groupsForUpdate ?? []);
        try {
            await addForm({
                workspaceId: workspaceId,
                groups: groups.map((group) => group.id),
                formId: form.formId
            }).unwrap();
            // show what was saved right away (the settings page reads the form from the store)
            if (openForm?.formId === form.formId) {
                dispatch(setForm({ ...openForm, groups }));
            }
            toast({ description: t(toastMessage.addedOnGroup).toString() });
        } catch (error) {
            toast({ description: t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
        }
    };
    return {
        deleteFormFromGroup,
        addFormOnGroup
    };
}