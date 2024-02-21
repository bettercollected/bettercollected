'use client';

import Validation from "@app/views/molecules/FormFields/Validation";
import {ValidationType} from "@app/views/molecules/FormFields/ValidationType";
import {Switch} from "@app/shadcn/components/ui/switch";

export default function FieldSettings() {

    return <div className="flex flex-col gap-4 px-4 py-6">
        <div className="p2-new text-black-700 !font-medium">
            Settings
        </div>
        <div className="flex justify-between w-full items-center">
            <div className="text-xs text-black-700">
                Required
            </div>
            <Switch/>
        </div>
        <Validation type={ValidationType.MIN_LENGTH}/>
        <Validation type={ValidationType.MAX_LENGTH}/>
        <Validation type={ValidationType.MIN_VALUE}/>
        <Validation type={ValidationType.MAX_VALUE}/>
        <Validation type={ValidationType.MIN_CHOICES}/>
        <Validation type={ValidationType.MAX_CHOICES}/>
    </div>
}