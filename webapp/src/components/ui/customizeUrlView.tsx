import React, { useState } from 'react';

import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';
import { PersistPartial } from 'redux-persist/es/persistReducer';

import { StandardFormDto } from '@app/models/dtos/form';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';

import { useModal } from '../modal-views/context';
import { ICustomizeUrlModalProps } from '../modal-views/modals/customize-url-modal';
import Button from './button/button';

export default function CustomizeUrlView({ description, url }: ICustomizeUrlModalProps) {
    const workspace = useAppSelector((state) => state.workspace);
    const form = useAppSelector((state: { form: StandardFormDto & PersistPartial }) => state.form);
    const customUrl = form?.settings?.customUrl || '';
    const [slot, setSlot] = useState(customUrl);
    const [isError, setError] = useState(false);
    const { closeModal } = useModal();
    const dispatch = useAppDispatch();
    const [patchFormSettings, { isLoading }] = usePatchFormSettingsMutation();
    const handleOnchange = (e: any) => {
        setSlot(e.target.value);
    };

    const handleUpdate = async () => {
        const body = {
            customUrl: slot
        };
        if (slot === '') {
            setError(true);
        } else {
            const response: any = await patchFormSettings({
                workspaceId: workspace.id,
                formId: form.formId,
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
            closeModal();
        }
    };
    return (
        <div className="w-full">
            <p className="sh1 ">Customize URL</p>
            <p className="pt-6  pb-8 !text-black-600">{description}</p>
            <p className=" mb-3 body1  !leading-none">
                Slug<span className="text-red-500">*</span>
            </p>
            <TextField
                InputProps={{
                    sx: {
                        height: '46px',
                        borderColor: '#0764EB !important'
                    }
                }}
                id="title"
                error={slot === '' && isError}
                placeholder="Eg. My form"
                className="w-full"
                value={slot}
                onChange={handleOnchange}
            />
            {slot === '' && isError && <p className="body4 !text-red-500 mt-2 h-[10px]">Slot is required</p>}
            <div className="px-10 py-6 gap-6 bg-blue-100 mt-8 md:w-[454px] w-full md:-ml-10">
                <p className="body1">New Link</p>
                <p className="body3 ">
                    <span className="text-black-600"> {url}</span>/<span className="text-black-800 font-medium">{slot}</span>
                </p>
            </div>
            <div className="mt-5 flex justify-end">
                <Button onClick={handleUpdate} isLoading={isLoading}>
                    Update URL
                </Button>
            </div>
        </div>
    );
}
