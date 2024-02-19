'use client';
import {useState} from "react";
import {Switch} from "@mui/material";
import {ValidationType} from "@app/views/molecules/FormFields/ValidationType";


const ValidationTypeTitle: {
    [type: string]: string
} = {
    [ValidationType.MAX_CHOICES]: "Maximum Choices",
    [ValidationType.MIN_CHOICES]: "Minimum Choices",
    [ValidationType.MAX_VALUE]: "Maximum Value",
    [ValidationType.MAX_LENGTH]: "Maximum Length",
    [ValidationType.MIN_VALUE]: "Minimum Value",
    [ValidationType.MIN_LENGTH]: "Minimum Length",
    [ValidationType.REGEX]: "Regex"
}

interface ValidationProps {
    field?: any
    type: ValidationType
}

export default function Validation({field, type}: ValidationProps) {

    const [checked, setChecked] = useState(false);

    const handleValidationValueChange = () => {

    }

    return <div className="flex  flex-col">
        <div className="flex body4 w-full justify-between items-center">
            <span className="text-xs text-black-700">{ValidationTypeTitle[type]}</span>
            <Switch
                checked={checked}
                onChange={() => {
                    setChecked(!checked);
                }}
            />
        </div>
        {checked && (
            <input
                onChange={handleValidationValueChange}
                value={""}
                type={"number"}
                placeholder={type === ValidationType.REGEX ? "Enter regex" : "Enter a number"}
                className="rounded-md mt-2 py-2 px-4 outline:none w-full border border-black-600 !text-black-900"
            />
        )}
    </div>
}