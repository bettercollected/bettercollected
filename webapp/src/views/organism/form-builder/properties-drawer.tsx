'use client';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@app/shadcn/components/ui/tabs';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import FieldSettings from '@app/views/organism/field-settings';
import FormSettingsTab from '@app/views/organism/form-builder/form-settings-tab';
import PageDesignTab from '@app/views/organism/form-builder/page-design-tab';
import PagePropertiesTab from '@app/views/organism/form-builder/page-properties-tab';

export default function PropertiesDrawer({ }: {}) {
    const { activeSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent } = useActiveFieldComponent();
    return (
        <div className="flex h-full flex-col border-l ">
            {activeFieldComponent?.id && (
                <>
                    <FieldSettings />
                </>
            )}
            {!activeFieldComponent?.id && activeSlideComponent?.id && (
                <>
                    <Tabs defaultValue="page" className="h-full w-full ">
                        <TabsList className="mx-2 my-2 w-[calc(100%-16px)]">
                            <TabsTrigger value="page" className="w-full">
                                Page
                            </TabsTrigger>
                            <TabsTrigger value="form" className="w-full">
                                Form
                            </TabsTrigger>
                            <TabsTrigger value="design" className="w-full">
                                Design
                            </TabsTrigger>
                        </TabsList>
                        <TabsContent value="page" className="border-b">
                            <PagePropertiesTab />
                        </TabsContent>
                        <TabsContent value="form">
                            <FormSettingsTab />
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
