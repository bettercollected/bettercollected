"use client"

import EllipsisOption from "@app/views/atoms/Icons/EllipsisOption";
import BetterCollectedSmallLogo from "@app/views/atoms/Icons/BetterCollectedSmallLogo";
import MenuDropdown from "@app/views/molecules/MenuDropDown";
import Button from "@app/views/atoms/Button";
import PlayIcon from "../atoms/Icons/PlayIcon";
import {ButtonVariant} from "@app/models/enums/button";
import {MenuItem} from "@mui/material";
import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";
import {v4} from "uuid"
import {FieldTypes} from "@app/models/dtos/form";

const formFields = [
    {name: "Short Input", type: FieldTypes.SHORT_TEXT},
    {name: "Email", type: FieldTypes.EMAIL},
    {name: "Number", type: FieldTypes.NUMBER}
]


const Navbar = () => {
    const {fields, addField} = useFieldSelectorAtom();

    return <div id="navbar" className="h-16 w-full border-b-[1px] border-b-black-100 bg-white p-4 flex justify-between">
        <div className={'flex gap-2 items-center'}>
            <div className={'px-4 py-[6px] rounded-lg shadow mr-4'}>
                <BetterCollectedSmallLogo/>
            </div>
            <h1>Contact Form</h1><EllipsisOption/></div>
        <div className={'flex gap-4 items-center'}>
            <MenuDropdown width={180} showExpandMore={false} id={"item-selector"} menuContent={
                <>
                    <div className={'rounded h-6 w-6 bg-black-400'}></div>
                    Insert</>
            } menuTitle={'Insert'}>
                {Array.isArray(formFields) && formFields.map((field) => {
                    return <MenuItem key={field.type}
                                     onClick={() => {
                                         const fieldId =v4()
                                         addField({
                                             id: fieldId,
                                             index: fields.length,
                                             type: field.type,
                                         })
                                         window.setTimeout(function () {
                                             document.getElementById(`input-${fieldId}`)?.focus()
                                         }, 0);

                                     }
                    }>
                        {field.name}
                    </MenuItem>
                })}
            </MenuDropdown>
            <MenuDropdown showExpandMore={false} id={"item-selector"} menuContent={
                <>
                    <div className={'rounded h-6 w-6 bg-black-400'}></div>
                    Media</>
            } menuTitle={'Media'}/>
            <MenuDropdown showExpandMore={false} id={"item-selector"} menuContent={
                <>
                    <div className={'rounded h-6 w-6 bg-black-400'}></div>
                    Text</>
            } menuTitle={'Text'}/>
        </div>
        <div className={'flex gap-2 items-center'}>
            <Button icon={<PlayIcon/>} variant={ButtonVariant.Tertiary}>
                Preview
            </Button>
            <Button>
                Publish
            </Button>

        </div>
    </div>
}
export default Navbar