import React, { useState } from 'react';

import { Divider } from '@mui/material';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';

import { usePatchPinnedFormMutation } from '@app/store/google/api';

interface FormSettingsProps {
    formId: string;
    form: any;
}

export default function FormSettingsTab({ form, formId }: FormSettingsProps) {
    const [patchPinnedForm] = usePatchPinnedFormMutation();
    const [isPinned, setIsPinned] = useState(!!form?.settings?.pinned);

    const [customUrl, setCustomUrl] = useState(form.settings.customUrl || '');

    const onSwitchChange = async (event: any) => {
        try {
            const response: any = await patchPinnedForm([{ form_id: formId, pinned: !isPinned }]);
            const updated = response?.data[0][formId] === 'True';
            console.info(updated);

            if (updated) {
                setIsPinned(!isPinned);
                toast(`Form ${!isPinned ? 'Pinned' : 'Unpinned'}`, {
                    type: 'success'
                });
            } else {
                toast('Error patching form', {
                    type: 'error'
                });
            }
        } catch (e) {
            toast('Error patching form', {
                type: 'error'
            });
        }
    };

    const onBlur = () => {};

    return (
        <div className="max-w-[600px]">
            <div className=" flex flex-col">
                <div className="text-xl font-bold text-black">Pinned</div>
                <div className="flex w-full justify-between items-center h-14 text-gray-800">
                    <div>Show this form in pinned section</div>
                    <Switch checked={isPinned} onClick={onSwitchChange} />
                </div>
            </div>
            <Divider className="mb-6 mt-2" />
            <div className=" flex flex-col ">
                <div className="text-xl font-bold text-black">Custom URL</div>
                <div className="flex w-full items-center justify-between text-gray-800">
                    <div>Something to show in url instead of id of form</div>
                    <TextField
                        size="small"
                        name="search-input"
                        placeholder="Custom-url"
                        value={customUrl}
                        onBlur={() => {
                            toast.success('On blur');
                        }}
                        onChange={(event) => {
                            setCustomUrl(event.target.value);
                        }}
                        className={'w-full max-w-[250px]'}
                    />
                </div>
            </div>
        </div>
    );
}
