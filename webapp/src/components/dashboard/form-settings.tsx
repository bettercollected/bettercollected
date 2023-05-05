import React, { useState } from 'react';

import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { FormSettingsCard } from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { StandardFormDto } from '@app/models/dtos/form';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';

export default function FormSettingsTab() {
    const form = useAppSelector((state) => state.form);
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const [customUrl, setCustomUrl] = useState(form?.settings?.customUrl || '');
    const [error, setError] = useState(false);
    const dispatch = useAppDispatch();

    const { openModal } = useModal();

    const patchSettings = async (body: any, f: StandardFormDto) => {
        const response: any = await patchFormSettings({
            workspaceId: workspace.id,
            formId: f.formId,
            body: body
        });
        if (response.data) {
            const settings = response.data.settings;
            dispatch(setFormSettings(settings));
            toast('Updated', { type: 'success' });
        } else {
            toast('Could not update this form setting!', { type: 'error' });
            return response.error;
        }
    };

    const onPinnedChange = (event: any, f?: StandardFormDto) => {
        if (!f) return toast('Could not update this form setting!', { type: 'error', toastId: 'errorToast' });
        patchSettings({ pinned: !f?.settings?.pinned }, f)
            .then((res) => {})
            .catch((e) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const onPrivateChanged = (event: any, f?: StandardFormDto) => {
        if (!f) return toast('Could not update this form setting!', { type: 'error', toastId: 'errorToast' });
        const patchBody = { private: !f?.settings?.private, pinned: false };
        patchSettings(patchBody, f)
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

        const isError = await patchSettings({ customUrl }, form);
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
                    <Switch data-testid="private-switch" checked={!!form?.settings?.private} onClick={(e) => onPrivateChanged(e, form)} />
                </div>
            </FormSettingsCard>
            {!form?.settings?.private && (
                <FormSettingsCard className="!p-6 !mt-5">
                    <div className=" flex items-center justify-between">
                        <div>
                            <div className="body1">Pinned</div>
                            <div className="body3">Show this form in pinned section</div>
                        </div>
                        <Switch data-testid="pinned-switch" checked={!!form?.settings?.pinned} onClick={(e) => onPinnedChange(e, form)} />
                    </div>
                </FormSettingsCard>
            )}

            {/* <FormSettingsCard>
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
            </FormSettingsCard> */}

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
                            openModal('DELETE_FORM_MODAL', { form, redirectToDashboard: true });
                        }}
                    >
                        Delete
                    </Button>
                </div>
            </FormSettingsCard>
        </div>
    );
}
