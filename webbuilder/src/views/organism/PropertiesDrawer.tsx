"use client";

import FieldSettings from "@app/views/organism/FieldSettings";
import {Divider, MenuItem, Select, Switch} from "@mui/material"

import {FieldTypes} from "@app/models/dtos/form"
import {useState} from "react";
import {useActiveFieldComponent, useActiveSlideComponent} from "@app/store/jotai/activeBuilderComponent";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@app/shadcn/components/ui/tabs";
import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";

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
                    <TabsContent value="page" className="px-4 border-b">
                        <div className="mt-6 text-black-700 p2-new !font-medium mb-4">
                            Layout
                        </div>
                        <div className="grid grid-cols-2 gap-2 pb-6 border-b">
                            {
                                [1, 2, 3].map((item) => (
                                    <div key={item} className="rounded-xl w-20 h-[50px] bg-gray-500">
                                    </div>)
                                )}

                        </div>
                        <div className="mt-6 text-black-700 p2-new !font-medium mb-4">
                            Settings
                        </div>
                        <div className="flex justify-between w-full items-center pb-4 border-b">
                            <div className="text-xs text-black-700">
                                Question Numbers
                            </div>
                            <Switch/>
                        </div>
                        <div className="mt-6 text-black-700 p2-new !font-medium mb-6">
                            Used Fields
                        </div>
                        <div className="flex flex-col mb-4 gap-6">
                            {
                                (activeSlideComponent?.index !== undefined) && formFields[activeSlideComponent.index]?.properties?.fields.map((field) => {
                                    return <div key={field.id}
                                                className="flex justify-between gap-2 items-center p4-new text-black-700">
                                        <div className="truncate">
                                            {field?.title || "Untitled Question"}
                                        </div>
                                        <svg width="20" height="20" viewBox="0 0 20 20" fill="none"
                                             xmlns="http://www.w3.org/2000/svg">
                                            <path d="M6 12.2695L14.0001 7.72927" stroke="#DBDBDB" strokeWidth="2"
                                                  strokeLinecap="round"/>
                                            <path d="M6 7.73047L14.0001 12.2707" stroke="#DBDBDB" strokeWidth="2"
                                                  strokeLinecap="round"/>
                                            <path d="M10 14L10 6" stroke="#DBDBDB" strokeWidth="2"
                                                  strokeLinecap="round"/>
                                        </svg>

                                    </div>
                                })
                            }
                            {
                                (activeSlideComponent?.index !== undefined) && (!formFields[activeSlideComponent.index]?.properties?.fields || !formFields[activeSlideComponent.index]?.properties?.fields?.length) &&
                                <div className="text-xs text-black-700">
                                    No form fields in this page. Add elements to this page will be shown here
                                </div>
                            }
                        </div>
                    </TabsContent>
                    <TabsContent value="design">
                    </TabsContent>
                </Tabs>
            </>
        }
    </div>
}

