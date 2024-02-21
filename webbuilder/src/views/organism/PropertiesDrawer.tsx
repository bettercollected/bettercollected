"use client";

import FieldSettings from "@app/views/organism/FieldSettings";
import {Divider, MenuItem, Select} from "@mui/material"

import {FieldTypes} from "@app/models/dtos/form"
import {useState} from "react";
import {useActiveFieldComponent, useActiveSlideComponent} from "@app/store/jotai/activeBuilderComponent";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@app/shadcn/components/ui/tabs";
import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";
import PagePropertiesTab from "@app/views/organism/PagePropertiesTab";
import PageDesignTab from "@app/views/organism/PageDesignTab";

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

    const {formFields} = useFieldSelectorAtom();


    const {activeSlideComponent} = useActiveSlideComponent()
    const {activeFieldComponent} = useActiveFieldComponent()

    return <div className="flex flex-col border-l h-full">
        {
            activeFieldComponent?.id && <>
                <FieldTypeSelector/>
                <Divider/>
                <FieldSettings/>
            </>
        }
        {
            !activeFieldComponent?.id && activeSlideComponent?.id && <>
                <Tabs defaultValue="page" className="w-full h-full">
                    <TabsList className="w-full my-2 px-2 ">
                        <TabsTrigger value="page" className="w-full">Page</TabsTrigger>
                        <TabsTrigger value="design" className="w-full">Design</TabsTrigger>
                    </TabsList>
                    <TabsContent value="page" className="border-b">
                        <PagePropertiesTab/>
                    </TabsContent>
                    <TabsContent value="design">
                        <PageDesignTab/>
                    </TabsContent>
                </Tabs>
            </>
        }
    </div>
}

