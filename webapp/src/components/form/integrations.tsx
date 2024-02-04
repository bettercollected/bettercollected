import {useRouter} from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import {ButtonVariant} from '@Components/Common/Input/Button/AppButtonProps';
import MuiSwitch from '@Components/Common/Input/Switch';
import {toast} from 'react-toastify';

import EmptyFormsView from '@app/components/dashboard/empty-form';
import {useModal} from '@app/components/modal-views/context';
import DeleteDropDown from '@app/components/ui/delete-dropdown';
import {Action} from '@app/models/dtos/actions';
import {
    useGetAllIntegrationsQuery,
    useRemoveActionFromFormMutation,
    useUpdateActionStatusInFormMutation
} from '@app/store/api-actions-api';
import {selectForm, setForm} from '@app/store/forms/slice';
import {useAppDispatch, useAppSelector} from '@app/store/hooks';
import {selectWorkspace} from '@app/store/workspaces/slice';

export default function FormIntegrations() {
    const {data} = useGetAllIntegrationsQuery({});

    const [removeActionFromForm] = useRemoveActionFromFormMutation();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const dispatch = useAppDispatch();
    const {openModal} = useModal();

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
                <div className="flex flex-col gap-[2px] mb-10">
                    <div className="h3-new text-black-800 mb-5">Integrations added to form</div>
                    {data?.map((integration, index) => (
                        <>
                            {addedActions.includes(integration.id) && (
                                <div key={`${integration?.id}_${index}`}
                                     className="flex items-center bg-black-100 py-4 px-5 rounded justify-between w-full">
                                    <div className="flex items-start justify-center flex-col gap-2">
                                        <div className="h4-new">{integration?.title || 'Untitled Integration'}</div>
                                        {integration?.description &&
                                            <div className="p2-new text-black-700">{integration.description}</div>}
                                        {integration?.parameters && getIntegrationIsAdded(integration) && (
                                            <div className="flex flex-col">
                                                {integration?.parameters?.map(
                                                    (parameter) =>
                                                        parameter?.required && (
                                                            <div key={parameter.name}
                                                                 className="flex items-center text-sm p2-new gap-2 mt-4">
                                                                <div className="font-bold text-sm">{parameter.name}</div>
                                                                :
                                                                <div
                                                                    className="text-black-700">{form?.parameters?.[integration.id]?.find((param: any) => param.name === parameter.name)?.value}</div>
                                                            </div>
                                                        )
                                                )}
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex gap-4 items-center">
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
                                                    toast('Updated', {type: 'success'});
                                                } else if (response?.error) {
                                                    toast('Could not update', {type: 'error'});
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
                                                    dispatch(setForm({...form, actions: response?.data}));
                                                    toast('Removed', {type: 'success'});
                                                } else if (response?.error) {
                                                    toast('Error', {type: 'error'});
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
                <div className="w-full flex flex-col gap-[2px]">
                    <div className="h3-new mb-8">Integrations</div>
                    {data?.map((integration, index) => (
                        <>
                            {(!addedActions || !addedActions.includes(integration.id)) && (
                                <div key={`${integration?.id}_${index}`}
                                     className="flex items-center bg-black-100 py-4 px-5 rounded justify-between w-full">
                                    <div className="flex items-start justify-center flex-col gap-2">
                                        <div className="h4-new">{integration?.title || 'Untitled Integration'}</div>
                                        {integration?.description &&
                                            <div className="p2-new text-black-700">{integration.description}</div>}
                                    </div>
                                    <div>
                                        <AppButton
                                            variant={ButtonVariant.Ghost}
                                            onClick={() => {
                                                openModal('ADD_ACTION_TO_FORM', {action: integration, form: form});
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
                    <EmptyFormsView description="No Integrations Found"/>
                </div>
            )}
        </div>
    );
}
