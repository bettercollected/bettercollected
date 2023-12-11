import MuiSwitch from '@Components/Common/Input/Switch';
import { toast } from 'react-toastify';

import { useAddActionToFormMutation, useGetAllIntegrationsQuery, useRemoveActionFromFormMutation } from '@app/store/api-actions-api';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function FormIntegrations() {
    const { data } = useGetAllIntegrationsQuery({});
    const [addActionToForm] = useAddActionToFormMutation();
    const [removeActionFromForm] = useRemoveActionFromFormMutation();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const dispatch = useAppDispatch();
    return (
        <>
            {data && Array.isArray(data) && (
                <div className="w-full px-2 md:px-10 lg:px-28 flex flex-col gap-[1px]">
                    {data?.map((integration: any, index) => (
                        <div key={`${integration?.id}_${index}`} className="flex items-center bg-black-100 py-4 px-5 rounded justify-between w-full">
                            <div className="flex items-start justify-center flex-col gap-2">
                                <div className="h4-new">{integration?.title || 'Untitled Integration'}</div>
                                {integration?.description && <div className="p2-new text-black-700">{integration.description}</div>}
                            </div>
                            <div>
                                <MuiSwitch
                                    checked={form?.actions?.on_submit?.includes(integration.id) || false}
                                    onChange={async (event, checked) => {
                                        let response: any;
                                        if (checked) {
                                            response = await addActionToForm({
                                                workspaceId: workspace.id,
                                                formId: form.formId,
                                                body: {
                                                    action_id: integration.id,
                                                    trigger: 'on_submit'
                                                }
                                            });
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
                                        } else {
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
