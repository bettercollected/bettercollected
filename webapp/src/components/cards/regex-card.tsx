import React from 'react';

import Plus from '@Components/Common/Icons/Plus';
import { Typography } from '@mui/material';

export default function RegexCard({ addRegex }: { addRegex: () => void }) {
    return (
        <div className=" p-6 bg-white  rounded">
            <div className="flex justify-between items-center">
                <p className="body1">Domain-Based Group Member</p>
                <div onClick={addRegex} className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                    <Plus className="h-4 w-4" />
                    <Typography className="!text-brand-500  body6">Add Regex</Typography>
                </div>
            </div>
            <p className="body4 !text-black-700">Auto add members based on common Domain address.</p>
            <p className="body4 !text-black-700">Eg: johndoe@yourdomain.any</p>
        </div>
    );
}
