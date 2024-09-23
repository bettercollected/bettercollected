import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import MuiSwitch from '@Components/Common/Input/Switch';
import { toast } from 'react-toastify';

import EmptyFormsView from '@Components/dashboard/empty-form';
import { useModal } from '@app/Components/modal-views/context';
import DeleteDropDown from '@app/Components/ui/delete-dropdown';
import { Action } from '@app/models/dtos/actions';
import { useGetAllIntegrationsQuery, useRemoveActionFromFormMutation, useUpdateActionStatusInFormMutation } from '@app/store/api-actions-api';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { selectAuth } from '@app/store/auth/slice';
import Image from 'next/image';

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
        return integrationState ? integrationState?.enabled : false;
    };

    const addedActions = form?.actions?.on_submit?.map((action: any) => action.id);

    const getIntegrationIsAdded = (integration: Action) => {
        const integrationState = form?.actions?.on_submit?.find((actionState: any) => actionState.id == integration.id);
        return !!integrationState;
    };

    return (
        <div className="mb-5 px-4 md:px-10 lg:px-28">
            {addedActions && addedActions.length > 0 && (
                <div className="mb-10 flex flex-col gap-2">
                    <div className="h3-new text-black-800 mb-5">Integrations added to form</div>
                    {data?.map((integration, index) => (
                        <>
                            {addedActions.includes(integration.id) && (
                                <div key={`${integration?.id}_${index}`} className="bg-black-50 mb-10 flex w-full flex-col items-start justify-between rounded px-5 py-4 shadow-lg sm:flex-row sm:items-center">
                                    <div className="flex items-start sm:items-center">
                                        {/*logo */}
                                        <Image src={integration?.url || '/integration/default.svg'} alt="logo" width={50} height={50} className="mr-4" />
                                        {/* Title and description */}
                                        <div className="mt-2 sm:mt-0">
                                            <h3 className="text-base font-semibold sm:text-lg">{integration?.title || 'Untitled Integration'}</h3>
                                            <p className="text-sm text-gray-600">{integration.description}</p>
                                            <span>
                                                {integration?.parameters && getIntegrationIsAdded(integration) && (
                                                    <div className="flex flex-col">
                                                        {integration?.parameters?.map(
                                                            (parameter) =>
                                                                parameter?.required && (
                                                                    <div key={parameter.name} className="p2-new mt-4 flex items-center gap-2 text-sm">
                                                                        <div className="whitespace-nowrap text-sm font-bold">{parameter.name}</div>:
                                                                        <div className="text-black-700 max-w-xs overflow-hidden text-ellipsis whitespace-nowrap sm:max-w-sm lg:max-w-md">
                                                                            {form?.parameters?.[integration.id]?.find((param: any) => param.name === parameter.name)?.value || 'N/A'}
                                                                        </div>
                                                                    </div>
                                                                )
                                                        )}
                                                    </div>
                                                )}
                                            </span>
                                        </div>
                                    </div>
                                    {/* Connect Button */}
                                    <div className="mt-4 flex items-center gap-2 sm:mt-0">
                                        {/* switch */}
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
                                        {/* Three dots dropdown */}
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
                <div className="flex w-full flex-col gap-2">
                    <div className="h3-new mb-8">Integrations</div>
                    {data?.map((integration, index) => (
                        <>
                            {(!addedActions || !addedActions.includes(integration.id)) && (
                                <div key={`${integration?.id}_${index}`} className="bg-black-50 mb-10 flex w-full flex-col items-start justify-between rounded px-5 py-4 shadow-lg sm:flex-row sm:items-center">
                                    <div className="flex items-start sm:items-center">
                                        {/* logo */}
                                        <Image src={integration?.url || '/integration/default.svg'} alt="logo" width={50} height={50} className="mr-4" />
                                        {/* title and description */}
                                        <div className="mt-2 sm:mt-0">
                                            <h3 className="text-base font-semibold sm:text-lg">{integration?.title || 'Untitled Integration'}</h3>
                                            <p className="text-sm text-gray-600">{integration.description}</p>
                                        </div>
                                    </div>
                                    <div className="mt-4 sm:mt-0">
                                        <AppButton
                                            data-umami-event="Add Integrations Button"
                                            data-umami-event-email={auth.email}
                                            variant={ButtonVariant.Primary}
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
