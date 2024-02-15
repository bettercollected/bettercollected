'use client';


import {Switch} from "@mui/material";

export default function FieldSettings() {

    return <div className="flex flex-col gap-4 p-4">
        <div className="p2-new text-black-700 !font-medium">
            Settings
        </div>
        <div className="flex justify-between w-full items-center">
            <div>
                Required
            </div>
            <Switch/>
        </div>
    </div>
}