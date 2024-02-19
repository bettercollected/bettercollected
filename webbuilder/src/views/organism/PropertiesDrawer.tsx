"use client";

import FieldSettings from "@app/views/organism/FieldSettings";
import {Divider, MenuItem, Select} from "@mui/material"

import {FieldTypes} from "@app/models/dtos/form"
import {useState} from "react";

const FieldTypeSelector = () => {

    const [selectedValue, setSelectedValue] = useState(FieldTypes.SHORT_TEXT)

    return <div className="flex flex-col gap-4 px-4 py-6">
        <div className="p2-new text-black-700 !font-medium">
            Type
        </div>
        <div>
            <Select fullWidth value={selectedValue} onChange={(event, child) => {
                setSelectedValue(event.target.value as FieldTypes)
            }}>
                {
                    Object.values(FieldTypes).map((fieldType) => {
                        return <MenuItem key={fieldType} value={fieldType}>
                            {fieldType}
                        </MenuItem>
                    })
                }
            </Select>
        </div>

    </div>
}

export default function PropertiesDrawer() {

    const shouldShowSettings = true

    const isTypeChangeable = true

    return <div className="flex flex-col border-l border-b-black-300 border-b">
        {
            isTypeChangeable && <>
                <FieldTypeSelector/>
                <Divider/>
            </>
        }
        {
            shouldShowSettings && <FieldSettings/>
        }

    </div>
}

