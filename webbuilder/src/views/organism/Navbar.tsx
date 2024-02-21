"use client"

import EllipsisOption from "@app/views/atoms/Icons/EllipsisOption";
import BetterCollectedSmallLogo from "@app/views/atoms/Icons/BetterCollectedSmallLogo";
import PlayIcon from "../atoms/Icons/PlayIcon";
import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";
import {toast} from "react-toastify";
import {formFieldsList} from "@app/constants/form-fields";
import { v4 } from "uuid"
import { FieldTypes } from "@app/models/dtos/form";
import { Button } from "@app/shadcn/components/ui/button";
import { useActiveSlideComponent } from "@app/store/jotai/activeBuilderComponent";
import { DropdownMenu } from "@app/shadcn/components/ui/dropdown-menu";

const fields = [
    { name: "Short Input", type: FieldTypes.SHORT_TEXT },
    { name: "Email", type: FieldTypes.EMAIL },
    { name: "Number", type: FieldTypes.NUMBER },
    { name: "File Upload", type: FieldTypes.FILE_UPLOAD },
    { name: "Link", type: FieldTypes.LINK },
    { name: 'Yes No', type: FieldTypes.YES_NO },
    { name: 'Drop Down', type: FieldTypes.DROP_DOWN },
    { name: 'Phone Number', type: FieldTypes.PHONE_NUMBER },
    { name: 'Multiple Choice', type: FieldTypes.MULTIPLE_CHOICE }
]

const Navbar = () => {
    const {formFields, addField} = useFieldSelectorAtom();
    const {activeSlideComponent} = useActiveSlideComponent()
    const handleAddField = (field: any) => {
        if (activeSlideComponent === null) {
            toast("Add a slide to add questions")
            return
        }
        const fieldId = v4()
        if (field.type === FieldTypes.YES_NO || field.type === FieldTypes.DROP_DOWN || field.type === FieldTypes.MULTIPLE_CHOICE) {
            const firstChoiceId = v4()
            const secondChoiceId = v4()
            addField({
                id: fieldId,
                index: formFields[activeSlideComponent.index]?.properties?.fields?.length ? formFields[activeSlideComponent.index]?.properties?.fields?.length! : 0,
                type: field.type,
                properties: {
                    fields: [],
                    choices: [
                        {id: firstChoiceId, value: field.type === FieldTypes.YES_NO ? "Yes" : ""},
                        {id: secondChoiceId, value: field.type === FieldTypes.YES_NO ? "No" : ""}
                    ]
                }
            }, activeSlideComponent?.index || 0)
        } else {
            addField({
                id: fieldId,
                index: formFields[activeSlideComponent!.index]?.properties?.fields?.length ? formFields[activeSlideComponent!.index]?.properties?.fields?.length! : 0,
                type: field.type,
            }, activeSlideComponent?.index || 0)
        }

        window.setTimeout(function () {
            document.getElementById(`input-${fieldId}`)?.focus()
        }, 0);
    }

    return <div id="navbar" className="h-16 w-full border-b-[1px] border-b-black-300 bg-white p-4 flex justify-between">
        <div className={'flex gap-2 items-center'}>
            <div className={'px-4 py-[6px] rounded-lg shadow mr-4'}>
                <BetterCollectedSmallLogo />
            </div>
            <input type="text" placeholder="Fill the Form Title" className='w-1/2 border-0' /><EllipsisOption /></div>
        <div className={'flex gap-4 items-center'}>
            <DropdownMenu>
                <DropdownMenu.Trigger tooltipLabel={'Insert Fields'}>
                    <div>
                        <div className={'rounded h-6 w-6 bg-black-400'}></div>
                        Insert
                    </div>
                </DropdownMenu.Trigger>
                <DropdownMenu.Content>
                    {Array.isArray(fields) && fields.map((field) => {
                        return <DropdownMenu.Item onClick={() => handleAddField(field)}>
                            {field.name}
                        </DropdownMenu.Item>
                    })}
                </DropdownMenu.Content>
            </DropdownMenu>
            <DropdownMenu >
                <DropdownMenu.Trigger tooltipLabel={'Add Media'}>
                    <div>
                        <div className={'rounded h-6 w-6 bg-black-400'}></div>
                        Media
                    </div>
                </DropdownMenu.Trigger>
            </DropdownMenu>
            <DropdownMenu >
                <DropdownMenu.Trigger tooltipLabel={'Insert Text'} >
                    <div>
                        <div className={'rounded h-6 w-6 bg-black-400'}></div>
                        Text
                    </div>
                </DropdownMenu.Trigger>
            </DropdownMenu>
        </div>
        <div className={'flex gap-2 items-center'}>
            <Button icon={<PlayIcon />} variant={'tertiary'}>
                Preview
            </Button>
            <Button>
                Publish
            </Button>

        </div>
    </div >
}
export default Navbar