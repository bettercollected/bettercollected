'use client';

import {Switch} from "@app/shadcn/components/ui/switch";
import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";

export default function FieldSettings() {

    const {updateFieldRequired, activeSlide, activeField} = useFieldSelectorAtom()

    return <div className="flex flex-col gap-4 px-4 py-6">
        <div className="p2-new text-black-700 !font-medium">
            Settings
        </div>
        <div className="flex justify-between w-full items-center">
            <div className="text-xs text-black-700">
                Description
            </div>
            <Switch checked={activeField?.description !== null} onCheckedChange={(checked)=>{

            }}/>
        </div>
        <div className="flex justify-between w-full items-center">
            <div className="text-xs text-black-700">
                Required
            </div>
            <Switch checked={activeField?.validations?.required || false} onCheckedChange={(checked) => {
                updateFieldRequired(activeField!.index, activeSlide!.index, checked)
            }}/>
        </div>
    </div>
}