import React, { useState } from 'react';

import { Divider } from '@mui/material';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';

import { Copy } from '@app/components/icons/copy';
import { ShareIcon } from '@app/components/icons/share-icon';
import environments from '@app/configs/environments';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';

interface FormSettingsProps {
    formId: string;
    form: any;
}

export default function FormSettingsTab({ form, formId }: FormSettingsProps) {
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const [isPinned, setIsPinned] = useState(!!form?.settings?.pinned);
    const workspace = useAppSelector((state) => state.workspace);
    const [customUrl, setCustomUrl] = useState(form.settings.customUrl || '');
    const isCustomDomain = !!workspace.customDomain;
    const [error, setError] = useState(false);
    const [_, copyToClipboard] = useCopyToClipboard();

    const patchSettings = (body: any) => {
        return patchFormSettings({
            workspaceId: workspace.id,
            formId: formId,
            body: body
        })
            .then((res) => {
                toast('Form Updated!!', { type: 'success' });
            })
            .catch((e) => {
                toast('Something went wrong!!', { type: 'error' });
            });
    };

    const onSwitchChange = (event: any) => {
        patchSettings({ pinned: !isPinned }).then((res) => {
            setIsPinned(!isPinned);
        });
    };

    const onBlur = () => {
        if (error) return;
        patchSettings({ customUrl });
    };

    return (
        <div className="max-w-[800px]">
            <div className=" flex flex-col">
                <div className="text-xl font-bold text-black">Pinned</div>
                <div className="flex w-full justify-between items-center h-14 text-gray-800">
                    <div>Show this form in pinned section</div>
                    <Switch checked={isPinned} onClick={onSwitchChange} />
                </div>
            </div>
            <Divider className="mb-6 mt-2" />
            <div className="flex justify-between items-start w-full">
                <div className={`text-xl font-bold w-full text-black mb-12`}>Custom Slug</div>
                <div className="w-full">
                    <TextField
                        size="medium"
                        name="search-input"
                        placeholder="Custom-url"
                        value={customUrl}
                        error={error}
                        onBlur={onBlur}
                        onChange={(event) => {
                            if (event.target.value && !event.target.value.match('^\\S+$')) {
                                setError(true);
                            } else {
                                setError(false);
                            }
                            setCustomUrl(event.target.value);
                        }}
                        className={`w-full`}
                    />
                    <div className="text-red-500 text-sm">{error && 'Custom Slug cannot contain spaces.'}</div>
                </div>
            </div>
            <div className="mt-5 space-y-2">
                <div className="text-gray-700 font-bold">Form URLs</div>
                <div className="text-gray-800 underline w-fit items-center rounded px-4 py-2 flex bg-gray-100">
                    {environments.CLIENT_HOST === 'localhost:3000' ? 'http' : 'https'}://{environments.CLIENT_HOST}/{workspace.workspaceName}/forms/{customUrl}
                    <Copy
                        width="16px"
                        height="16px"
                        className="ml-4 cursor-pointer"
                        onClick={() => {
                            copyToClipboard(`${environments.CLIENT_HOST === 'localhost:3000' ? 'http' : 'https'}://${environments.CLIENT_HOST}/${workspace.workspaceName}/forms/${customUrl}`);
                            toast('Copied Form Url', {
                                type: 'info'
                            });
                        }}
                    />
                </div>
                {isCustomDomain && (
                    <div className="text-gray-800 underline w-fit items-center rounded px-4 py-2 flex bg-gray-100">
                        {environments.CLIENT_HOST === 'localhost:3000' ? 'http' : 'https'}://{workspace.customDomain}/forms/{customUrl}
                        <Copy
                            width="16px"
                            height="16px"
                            className="ml-4 cursor-pointer"
                            onClick={() => {
                                copyToClipboard(`${environments.CLIENT_HOST === 'localhost:3000' ? 'http' : 'https'}://${workspace.customDomain}/forms/${customUrl}`);
                                toast('Form Url Copied', {
                                    type: 'info'
                                });
                            }}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
