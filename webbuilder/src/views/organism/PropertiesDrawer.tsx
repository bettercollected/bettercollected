'use client';

import { useState } from 'react';

import { Divider, MenuItem, Select } from '@mui/material';

import { formFieldsList } from '@app/constants/form-fields';
import { FieldTypes } from '@app/models/dtos/form';
import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger
} from '@app/shadcn/components/ui/tabs';
import {
    useActiveFieldComponent,
    useActiveSlideComponent
} from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import FieldSettings from '@app/views/organism/FieldSettings';
import PageDesignTab from '@app/views/organism/PageDesignTab';
import PagePropertiesTab from '@app/views/organism/PagePropertiesTab';

const FieldTypeSelector = () => {
    const [selectedValue, setSelectedValue] = useState(FieldTypes.SHORT_TEXT);

    return (
        <div className="flex flex-col gap-4 px-4 py-6">
            <div className="p2-new !font-medium text-black-700">Type</div>
            <div>
                <Select
                    fullWidth
                    value={selectedValue}
                    onChange={(event, child) => {
                        setSelectedValue(event.target.value as FieldTypes);
                    }}
                >
                    {formFieldsList.map((fieldType) => {
                        return (
                            <MenuItem
                                className="flex gap-2"
                                key={fieldType.name}
                                value={fieldType.type}
                            >
                                <span className="h-4 w-4 rounded-md bg-black-300" />
                                {fieldType.name}
                            </MenuItem>
                        );
                    })}
                </Select>
            </div>
        </div>
    );
};

export default function PropertiesDrawer() {
    const { formFields } = useFormFieldsAtom();

    const { activeSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent } = useActiveFieldComponent();

    return (
        <div className="flex h-full flex-col border-l ">
            {activeFieldComponent?.id && (
                <>
                    <FieldTypeSelector />
                    <Divider />
                    <FieldSettings />
                </>
            )}
            {!activeFieldComponent?.id && activeSlideComponent?.id && (
                <>
                    <Tabs defaultValue="page" className="h-full w-full ">
                        <TabsList className="my-2 w-full px-2 ">
                            <TabsTrigger value="page" className="w-full">
                                Page
                            </TabsTrigger>
                            <TabsTrigger value="design" className="w-full">
                                Design
                            </TabsTrigger>
                        </TabsList>
                        <TabsContent value="page" className="border-b">
                            <PagePropertiesTab />
                        </TabsContent>
                        <TabsContent value="design">
                            <PageDesignTab />
                        </TabsContent>
                    </Tabs>
                </>
            )}
        </div>
    );
}
