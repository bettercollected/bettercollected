import React, { useState } from 'react';

import { Divider } from '@mui/material';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';

import { Copy } from '@app/components/icons/copy';
import { ShareIcon } from '@app/components/icons/share-icon';
import { useModal } from '@app/components/modal-views/context';
import SettingsCard, { FormSettingsCard } from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { toEndDottedStr, toMidDottedStr } from '@app/utils/stringUtils';

export default function FormSettingsTab() {
    const form = useAppSelector((state) => state.form);
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const [customUrl, setCustomUrl] = useState(form?.settings?.customUrl || '');
    const isCustomDomain = !!workspace.customDomain;
    const [error, setError] = useState(false);
    const [_, copyToClipboard] = useCopyToClipboard();
    const dispatch = useAppDispatch();

    const { openModal } = useModal();

    const patchSettings = async (body: any) => {
        const response: any = await patchFormSettings({
            workspaceId: workspace.id,
            formId: form.formId,
            body: body
        });
        if (response.data) {
            const settings = response.data.settings;
            dispatch(setFormSettings(settings));
            toast('Form Updated!!', { type: 'success', toastId: 'successToast' });
        } else {
            toast('Something went wrong.', { type: 'error' });
            return response.error;
        }
    };

    const onPinnedChange = (event: any) => {
        patchSettings({ pinned: !form?.settings?.pinned })
            .then((res) => {})
            .catch((e) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const onPrivateChanged = () => {
        patchSettings({ private: !form?.settings?.private })
            .then((res) => {})
            .catch((e: any) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const onBlur = async () => {
        if (!customUrl) {
            setCustomUrl(form.settings?.customUrl || form.formId);
            setError(false);
        }
        if (error || form.settings?.customUrl === customUrl || !customUrl) return;

        const isError = await patchSettings({ customUrl });
        if (isError) {
            setError(true);
        }
    };
    return (
        <div>
            <FormSettingsCard className="!p-6 !mt-5">
                <div className=" flex items-center justify-between">
                    <div>
                        <div className="body1">Hide Form</div>
                        <div className="body3">Do not show this form in workspace page.</div>
                    </div>
                    <Switch data-testid="private-switch" checked={!!form?.settings?.private} onClick={onPrivateChanged} />
                </div>
            </FormSettingsCard>
            {!form?.settings?.private && (
                <FormSettingsCard className="!p-6 !mt-5">
                    <div className=" flex items-center justify-between">
                        <div>
                            <div className="body1">Pinned</div>
                            <div className="body3">Show this form in pinned section</div>
                        </div>
                        <Switch data-testid="pinned-switch" checked={!!form?.settings?.pinned} onClick={onPinnedChange} />
                    </div>
                </FormSettingsCard>
            )}

            <FormSettingsCard>
                <div className="flex justify-between items-center w-full">
                    <span className={`body1 flex-1`}>Custom Slug</span>
                    <div className="w-full flex-1">
                        <TextField
                            size="medium"
                            name="search-input"
                            placeholder="Custom-url"
                            value={customUrl}
                            error={error}
                            onBlur={onBlur}
                            onChange={(event) => {
                                if (!event.target.value || !event.target.value.match('^\\S+$')) {
                                    setError(true);
                                } else {
                                    setError(false);
                                }
                                setCustomUrl(event.target.value);
                            }}
                            className={`w-full `}
                        />
                    </div>
                </div>
            </FormSettingsCard>

            <FormSettingsCard>
                <div className="flex items-center justify-between">
                    <div className="">
                        <div className="body1">Delete Form</div>
                        <div className="body3">
                            <div>Deleting this form will also remove all the responses and deletion requests.</div>
                        </div>
                    </div>
                    <Button
                        data-testid="logout-button"
                        variant="solid"
                        size="medium"
                        color="danger"
                        onClick={() => {
                            openModal('DELETE_FORM_MODAL', { form });
                        }}
                    >
                        Delete
                    </Button>
                </div>
            </FormSettingsCard>
        </div>
    );
}
