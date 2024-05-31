import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import MuiSwitch from '@Components/Common/Input/Switch';
import { toast } from 'react-toastify';

import EmptyFormsView from '@app/components/dashboard/empty-form';
import { useModal } from '@app/components/modal-views/context';
import DeleteDropDown from '@app/components/ui/delete-dropdown';
import { Action } from '@app/models/dtos/actions';
import { useGetAllIntegrationsQuery, useRemoveActionFromFormMutation, useUpdateActionStatusInFormMutation } from '@app/store/api-actions-api';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { selectAuth } from '@app/store/auth/slice';

export default function FormIntegrations() {
    const { data } = useGetAllIntegrationsQuery({});
    const [removeActionFromForm] = useRemoveActionFromFormMutation();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const dispatch = useAppDispatch();
    const { openModal } = useModal();
    const auth = useAppSelector(selectAuth);

    const router = useRouter();

    const [updateAction] = useUpdateActionStatusInFormMutation();
    const getIntegrationEnabled = (integration: Action) => {
        const integrationState = form?.actions?.on_submit?.find((actionState: any) => actionState.id == integration.id);
        if (!integrationState) return false;
        else return integrationState?.enabled;
    };

    const addedActions = form?.actions?.on_submit?.map((action: any) => action.id);

    const getIntegrationIsAdded = (integration: Action) => {
        const integrationState = form?.actions?.on_submit?.find((actionState: any) => actionState.id == integration.id);
        return !!integrationState;
    };

    return (
        <div className="md:px-10 lg:px-28">
            {addedActions && addedActions.length > 0 && (
                <div className="mb-10 flex flex-col gap-[2px]">
                    <div className="h3-new text-black-800 mb-5">Integrations added to form</div>
                    {data?.map((integration, index) => (
                        <>
                            {addedActions.includes(integration.id) && (
                                <div key={`${integration?.id}_${index}`} className="bg-black-100 flex w-full items-center justify-between rounded px-5 py-4">
                                    <div className="flex flex-col items-start justify-center gap-2">
                                        <div className="h4-new">{integration?.title || 'Untitled Integration'}</div>
                                        {integration?.description && <div className="p2-new text-black-700">{integration.description}</div>}
                                        {integration?.parameters && getIntegrationIsAdded(integration) && (
                                            <div className="flex flex-col">
                                                {integration?.parameters?.map(
                                                    (parameter) =>
                                                        parameter?.required && (
                                                            <div key={parameter.name} className="p2-new mt-4 flex items-center gap-2 text-sm">
                                                                <div className="text-sm font-bold">{parameter.name}</div>:<div className="text-black-700">{form?.parameters?.[integration.id]?.find((param: any) => param.name === parameter.name)?.value}</div>
                                                            </div>
                                                        )
                                                )}
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <MuiSwitch
                                            checked={getIntegrationEnabled(integration)}
                                            onChange={async (event, checked) => {
                                                const update_type = checked ? 'enable' : 'disable';
                                                const response: any = await updateAction({
                                                    workspaceId: workspace.id,
                                                    formId: form.formId,
                                                    body: {
                                                        action_id: integration.id,
                                                        update_type: update_type
                                                    }
                                                });

                                                if (response?.data) {
                                                    router.push(router.asPath);
                                                    toast('Updated', { type: 'success' });
                                                } else if (response?.error) {
                                                    toast('Could not update', { type: 'error' });
                                                }
                                            }}
                                        />
                                        <DeleteDropDown
                                            onDropDownItemClick={async () => {
                                                const response: any = await removeActionFromForm({
                                                    workspaceId: workspace.id,
                                                    formId: form.formId,
                                                    actionId: integration.id
                                                });

                                                if (response?.data) {
                                                    dispatch(setForm({ ...form, actions: response?.data }));
                                                    toast('Removed', { type: 'success' });
                                                } else if (response?.error) {
                                                    toast('Error', { type: 'error' });
                                                }
                                            }}
                                        />
                                    </div>
                                </div>
                            )}
                        </>
                    ))}
                </div>
            )}
            {data && Array.isArray(data) && data?.length !== addedActions?.length && (
                <div className="flex w-full flex-col gap-[2px]">
                    <div className="h3-new mb-8">Integrations</div>
                    {data?.map((integration, index) => (
                        <>
                            {(!addedActions || !addedActions.includes(integration.id)) && (
                                <div key={`${integration?.id}_${index}`} className="bg-black-100 flex w-full items-center justify-between rounded px-5 py-4">
                                    <div className="flex flex-col items-start justify-center gap-2">
                                        <div className="h4-new">{integration?.title || 'Untitled Integration'}</div>
                                        {integration?.description && <div className="p2-new text-black-700">{integration.description}</div>}
                                    </div>
                                    <div>
                                        <AppButton
                                            data-umami-event="Add Integrations Button"
                                            data-umami-event-email={auth.email}
                                            variant={ButtonVariant.Ghost}
                                            onClick={() => {
                                                openModal('ADD_ACTION_TO_FORM', { action: integration, form: form });
                                            }}
                                        >
                                            {' '}
                                            Add to Form
                                        </AppButton>
                                    </div>
                                </div>
                            )}
                        </>
                    ))}
                </div>
            )}
            {Array.isArray(data) && data.length == 0 && (
                <div>
                    <EmptyFormsView description="No Integrations Found" />
                </div>
            )}
        </div>
    );
}
