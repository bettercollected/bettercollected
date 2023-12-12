import MuiSwitch from '@Components/Common/Input/Switch';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { useAddActionToFormMutation, useGetAllIntegrationsQuery, useRemoveActionFromFormMutation } from '@app/store/api-actions-api';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function FormIntegrations() {
    const { data } = useGetAllIntegrationsQuery({});
    const [removeActionFromForm] = useRemoveActionFromFormMutation();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const dispatch = useAppDispatch();
    const { openModal } = useModal();
    return (
        <>
            {data && Array.isArray(data) && (
                <div className="w-full px-2 md:px-10 lg:px-28 flex flex-col gap-[1px]">
                    {data?.map((integration, index) => (
                        <div key={`${integration?.id}_${index}`} className="flex items-center bg-black-100 py-4 px-5 rounded justify-between w-full">
                            <div className="flex items-start justify-center flex-col gap-2">
                                <div className="h4-new">{integration?.title || 'Untitled Integration'}</div>
                                {integration?.description && <div className="p2-new text-black-700">{integration.description}</div>}
                                {integration?.parameters && (
                                    <div className="flex flex-col gap-2">
                                        {integration?.parameters?.map(
                                            (parameter) =>
                                                parameter?.required && (
                                                    <div key={parameter.name} className="flex items-center text-sm p2-new gap-2">
                                                        <div className="font-bold text-sm">{parameter.name}</div>:<div className="text-black-700">{form?.parameters?.[integration.id].find((param: any) => param.name === parameter.name)?.value}</div>
                                                    </div>
                                                )
                                        )}
                                    </div>
                                )}
                            </div>
                            <div>
                                <MuiSwitch
                                    checked={form?.actions?.on_submit?.includes(integration.id) || false}
                                    onChange={async (event, checked) => {
                                        let response: any;
                                        if (checked) {
                                            openModal('ADD_ACTION_TO_FORM', { action: integration, form: form });
                                        } else {
                                            response = await removeActionFromForm({
                                                workspaceId: workspace.id,
                                                formId: form.formId,
                                                actionId: integration.id
                                            });
                                        }

                                        if (response?.data) {
                                            dispatch(setForm({ ...form, actions: response?.data }));
                                            toast(checked ? 'Added' : 'Removed', { type: 'success' });
                                        } else if (response?.error) {
                                            toast('Error', { type: 'error' });
                                        }
                                    }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </>
    );
}
