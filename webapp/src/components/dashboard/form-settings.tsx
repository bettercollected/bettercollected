import React, { useState } from 'react';

import { Divider } from '@mui/material';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';

import { Copy } from '@app/components/icons/copy';
import { ShareIcon } from '@app/components/icons/share-icon';
import environments from '@app/configs/environments';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';

export default function FormSettingsTab() {
    const form = useAppSelector((state) => state.form);
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const [isPinned, setIsPinned] = useState(!!form?.settings?.pinned);
    const [isPrivate, setIsPrivate] = useState(!!form?.settings?.private);
    const workspace = useAppSelector((state) => state.workspace);
    const [customUrl, setCustomUrl] = useState(form?.settings?.customUrl || '');
    const isCustomDomain = !!workspace.customDomain;
    const [error, setError] = useState(false);
    const [_, copyToClipboard] = useCopyToClipboard();
    const dispatch = useAppDispatch();

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
        } else if (response.error) {
            setError(true);
            toast(response.error.data, { type: 'error', toastId: 'errorToast' });
        }
    };

    const onPinnedChange = (event: any) => {
        patchSettings({ pinned: !isPinned }).then((res) => {
            setIsPinned(!isPinned);
        });
    };

    const onPrivateChanged = () => {
        patchSettings({ private: !isPrivate }).then((res) => {
            setIsPrivate(!isPrivate);
        });
    };

    const onBlur = () => {
        if (!customUrl) {
            setCustomUrl(form.settings?.customUrl || form.formId);
            setError(false);
        }
        if (error || form.settings?.customUrl === customUrl || !customUrl) return;

        patchSettings({ customUrl }).catch((e) => {});
    };

    const getFirstFiveSlugName = (slug: any) => {
        if (slug.length <= 5) return slug;
        const firstPart = slug.substring(0, 3);
        const lastPart = slug.substring(slug.length - 2);
        return `${firstPart}..${lastPart}`;
    };

    return (
        <div className="max-w-[800px]">
            <div className=" flex flex-col">
                <div className="text-xl font-bold text-black">Pinned</div>
                <div className="flex w-full justify-between items-center h-14 text-gray-800">
                    <div>Show this form in pinned section</div>
                    <Switch data-testid="pinned-switch" checked={isPinned} onClick={onPinnedChange} />
                </div>
            </div>
            <div className=" flex flex-col">
                <div className="text-xl font-bold text-black">Hide Form</div>
                <div className="flex w-full justify-between items-center h-14 text-gray-800">
                    <div>Do not show this form in workspace page.</div>
                    <Switch data-testid="private-switch" checked={isPrivate} onClick={onPrivateChanged} />
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
                            if (!event.target.value || !event.target.value.match('^\\S+$')) {
                                setError(true);
                            } else {
                                setError(false);
                            }
                            setCustomUrl(event.target.value);
                        }}
                        className={`w-full`}
                    />
                </div>
            </div>
            <div className="mt-5 space-y-2">
                <div className="text-gray-700 font-bold">Form URLs</div>
                <div className="text-gray-800 space-x-4 underline w-fit items-center rounded px-4 py-2 flex bg-gray-100">
                    <p>
                        {environments.CLIENT_HOST === 'localhost:3000' ? 'http' : 'https'}://{environments.CLIENT_HOST}/{workspace.workspaceName}/forms/{getFirstFiveSlugName(customUrl)}
                    </p>
                    <Copy
                        width="16px"
                        height="16px"
                        className="cursor-pointer"
                        onClick={() => {
                            copyToClipboard(`${environments.CLIENT_HOST === 'localhost:3000' ? 'http' : 'https'}://${environments.CLIENT_HOST}/${workspace.workspaceName}/forms/${customUrl}`);
                            toast('Form URL Copied', {
                                type: 'info'
                            });
                        }}
                    />
                    <a href={`${environments.CLIENT_HOST === 'localhost:3000' ? 'http' : 'https'}://${environments.CLIENT_HOST}/${workspace.workspaceName}/forms/${customUrl}`} target="_blank" referrerPolicy="no-referrer-when-downgrade" rel="noreferrer">
                        <ShareIcon width={19} height={19} />
                    </a>
                </div>
                {isCustomDomain && (
                    <div className="text-gray-800 underline space-x-4 w-fit items-center rounded px-4 py-2 flex bg-gray-100">
                        <p className="text-ellipsis whitespace-pre-wrap">
                            {environments.CLIENT_HOST === 'localhost:3000' ? 'http' : 'https'}://{workspace.customDomain}/forms/{getFirstFiveSlugName(customUrl)}
                        </p>
                        <Copy
                            width="16px"
                            height="16px"
                            className="cursor-pointer"
                            onClick={() => {
                                copyToClipboard(`${environments.CLIENT_HOST === 'localhost:3000' ? 'http' : 'https'}://${workspace.customDomain}/forms/${customUrl}`);
                                toast('Form URL Copied', {
                                    type: 'info'
                                });
                            }}
                        />
                        <a href={`${environments.CLIENT_HOST === 'localhost:3000' ? 'http' : 'https'}://${workspace.customDomain}/forms/${customUrl}`} target="_blank" referrerPolicy="no-referrer-when-downgrade" rel="noreferrer">
                            <ShareIcon width={19} height={19} />
                        </a>
                    </div>
                )}
            </div>
        </div>
    );
}
