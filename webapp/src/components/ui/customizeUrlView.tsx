import React, { useState } from 'react';

import TextField from '@mui/material/TextField';

import { ICustomizeUrlModalProps } from '../modal-views/modals/customize-url-modal';
import Button from './button/button';

export default function CustomizeUrlView({ description, domain }: ICustomizeUrlModalProps) {
    const [slot, setSlot] = useState('');
    const [isError, setError] = useState(false);
    const handleOnchange = (e: any) => {
        setSlot(e.target.value);
    };
    const handleUpdate = () => {
        if (slot === '') {
            setError(true);
        }
    };
    return (
        <div className="w-[370px]">
            <p className="sh1 ">Customize URL</p>
            <p className="pt-6  pb-8 !text-black-600">{description}</p>
            <p className=" mb-3 body1  !leading-none">
                Slot<span className="text-red-500">*</span>
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
            <div className="px-10 py-6 gap-6 bg-blue-100 mt-8">
                <p className="body1">New Link</p>
                <p className="body3 ">
                    <span className="text-black-600"> {domain}</span>/<span className="text-black-800 font-medium">{slot}</span>
                </p>
            </div>
            <div className="mt-5 flex justify-end">
                <Button onClick={handleUpdate}>Update Url</Button>
            </div>
        </div>
    );
}
