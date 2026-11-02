import Image from 'next/image';
import { useRouter } from 'next/navigation';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';

import EmptyFormsView from '@app/components/dashboard/empty-form';
import SheetsReconnectNotice, { SheetsReconnectBadge, useSheetsNeedsReconnect } from '@app/components/form-integrations/sheets-reconnect-notice';
import { useModal } from '@app/components/modal-views/context';
import DeleteDropDown from '@app/components/ui/delete-dropdown';
import { localesCommon } from '@app/constants/locales/common';
import { Action } from '@app/models/dtos/actions';
import { Switch } from '@app/shadcn/components/ui/switch';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useGetAllIntegrationsQuery, useRemoveActionFromFormMutation, useUpdateActionStatusInFormMutation } from '@app/store/api-actions-api';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

type ReconnectTarget = Parameters<typeof useSheetsNeedsReconnect>[0];

// The Google Sheets action asks its reconnect status when it is listed (the
// two parts below share one request); nothing shows when it is not needed.
function ReconnectBadge(props: ReconnectTarget) {
    return useSheetsNeedsReconnect(props) ? <SheetsReconnectBadge /> : null;
}

function ReconnectNotice({ onReconnect, ...target }: ReconnectTarget & { onReconnect: () => void }) {
    return useSheetsNeedsReconnect(target) ? <SheetsReconnectNotice onReconnect={onReconnect} className="mt-4 sm:basis-full" /> : null;
}

/**
 * The actions of a form (Google Sheets and the like): the added ones with their
 * on/off switch and menu, the ones not added yet with an "Add to Form" button.
 * In a card's side sheet, `onlyActionId` shows just that action and `headless`
 * leaves out the section's own title.
 */
export default function FormIntegrations({ onlyActionId, headless = false }: { onlyActionId?: string; headless?: boolean }) {
    const { t } = useTranslation();
    const { data } = useGetAllIntegrationsQuery({});
    const { toast } = useToast();
    const [removeActionFromForm] = useRemoveActionFromFormMutation();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const dispatch = useAppDispatch();
    const { openModal } = useModal();

    const router = useRouter();

    const [updateAction] = useUpdateActionStatusInFormMutation();
    const getIntegrationEnabled = (integration: Action) => {
        const integrationState = form?.actions?.on_submit?.find((actionState: any) => actionState.id == integration.id);
        return integrationState ? integrationState?.enabled : false;
    };

    const addedActions: string[] = form?.actions?.on_submit?.map((action: any) => action.id) ?? [];
    const listed: Action[] = Array.isArray(data) ? (onlyActionId ? data.filter((integration) => integration.id === onlyActionId) : data) : [];
    // Two lists of plain elements, each keyed by the action's id (no bare fragments in a list).
    const added = listed.filter((integration) => addedActions.includes(integration.id));
    const notAdded = listed.filter((integration) => !addedActions.includes(integration.id));

    return (
        <div className="mb-5">
            {added.length > 0 && (
                <div className="mb-10 flex flex-col gap-2">
                    {!headless && <div className="h3-new text-black-800 mb-5">{t('STAFF.INTEGRATIONS.ADDED_TITLE')}</div>}
                    {added.map((integration) => (
                        <div
                            key={integration.id}
                            className="bg-black-50 mb-10 flex w-full flex-col flex-wrap items-start justify-between rounded border border-black-300 px-5 py-4 sm:flex-row sm:items-center"
                        >
                            <div className="flex min-w-0 max-w-full items-start sm:flex-1 sm:items-center">
                                {/*logo */}
                                <Image src={integration?.url || '/integration/default.svg'} alt="" width={50} height={50} className="mr-4 shrink-0" />
                                {/* Title and description */}
                                <div className="mt-2 min-w-0 sm:mt-0">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h3 className="text-base font-semibold sm:text-lg">{integration?.title || t('STAFF.INTEGRATIONS.UNTITLED')}</h3>
                                        <ReconnectBadge workspaceId={workspace?.id} formId={form?.formId} action={integration} />
                                    </div>
                                    <p className="text-sm text-gray-600 break-words">{integration.description}</p>
                                    {integration?.parameters && (
                                        <div className="flex flex-col">
                                            {integration?.parameters?.map(
                                                (parameter) =>
                                                    parameter?.required && (
                                                        <div key={parameter.name} className="p2-new mt-4 flex items-center gap-2 text-sm">
                                                            <div className="whitespace-nowrap font-mono text-[13px] font-semibold">{parameter.name}</div>:
                                                            <div className="text-black-700 min-w-0 font-mono text-[13px] max-w-xs overflow-hidden text-ellipsis whitespace-nowrap sm:max-w-sm lg:max-w-md">
                                                                {form?.parameters?.[integration.id]?.find((param: any) => param.name === parameter.name)?.value || 'N/A'}
                                                            </div>
                                                        </div>
                                                    )
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                            {/* Connect Button */}
                            <div className="mt-4 flex items-center gap-2 sm:mt-0">
                                <Switch
                                    aria-label={t(localesCommon.turnOnOff, { name: integration?.title || t('STAFF.INTEGRATIONS.UNTITLED') })}
                                    checked={getIntegrationEnabled(integration)}
                                    onCheckedChange={async (checked) => {
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
                                            router.refresh();
                                            toast({ description: t('STAFF.INTEGRATIONS.UPDATED') });
                                        } else if (response?.error) {
                                            toast({ description: t('STAFF.INTEGRATIONS.UPDATE_FAILED'), variant: 'destructive' });
                                        }
                                    }}
                                />
                                {/* Three dots dropdown */}
                                <DeleteDropDown
                                    itemName={integration?.title || t('STAFF.INTEGRATIONS.UNTITLED')}
                                    onDropDownItemClick={async () => {
                                        const response: any = await removeActionFromForm({
                                            workspaceId: workspace.id,
                                            formId: form.formId,
                                            actionId: integration.id
                                        });

                                        if (response?.data) {
                                            dispatch(setForm({ ...form, actions: response?.data }));
                                            toast({ description: t('STAFF.INTEGRATIONS.REMOVED') });
                                        } else if (response?.error) {
                                            toast({ description: t('STAFF.COMMON.SOMETHING_WRONG'), variant: 'destructive' });
                                        }
                                    }}
                                />
                            </div>
                            {/* Reconnect notice, on its own row under the action */}
                            <ReconnectNotice
                                workspaceId={workspace?.id}
                                formId={form?.formId}
                                action={integration}
                                onReconnect={() => openModal('ADD_ACTION_TO_FORM', { action: integration, form: form, reconnect: true })}
                            />
                        </div>
                    ))}
                </div>
            )}
            {notAdded.length > 0 && (
                <div className="flex w-full flex-col gap-2">
                    {notAdded.map((integration) => (
                        <div key={integration.id} className="bg-black-50 mb-10 flex w-full flex-col items-start justify-between rounded border border-black-300 px-5 py-4 sm:flex-row sm:items-center">
                            <div className="flex min-w-0 items-start sm:items-center">
                                {/* logo */}
                                <Image src={integration?.url || '/integration/default.svg'} alt="" width={50} height={50} className="mr-4 shrink-0" />
                                {/* title and description */}
                                <div className="mt-2 min-w-0 sm:mt-0">
                                    <h3 className="text-base font-semibold sm:text-lg">{integration?.title || t('STAFF.INTEGRATIONS.UNTITLED')}</h3>
                                    <p className="text-sm text-gray-600 break-words">{integration.description}</p>
                                </div>
                            </div>
                            <div className="mt-4 sm:mt-0">
                                <Button
                                    data-umami-event="Add Integrations Button"
                                    variant="primary"
                                    onClick={() => {
                                        openModal('ADD_ACTION_TO_FORM', { action: integration, form: form });
                                    }}
                                >
                                    {t('STAFF.INTEGRATIONS.ADD')}
                                </Button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
            {Array.isArray(data) && data.length == 0 && !onlyActionId && (
                <div>
                    <EmptyFormsView description={t('STAFF.INTEGRATIONS.NONE')} />
                </div>
            )}
        </div>
    );
}
