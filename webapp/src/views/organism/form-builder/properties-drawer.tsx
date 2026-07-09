'use client';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@app/shadcn/components/ui/tabs';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { PropertiesTab, usePropertiesTab } from '@app/store/jotai/properties-tab';
import FieldSettings from '@app/views/organism/field-settings';
import FormSettingsTab from '@app/views/organism/form-builder/form-settings-tab';
import AIChatTab from '@app/views/organism/form-builder/ai-chat-tab';
import PageDesignTab from '@app/views/organism/form-builder/page-design-tab';
import PagePropertiesTab from '@app/views/organism/form-builder/page-properties-tab';

export default function PropertiesDrawer({ }: {}) {
    const { activeSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent } = useActiveFieldComponent();
    const { propertiesTab, setPropertiesTab } = usePropertiesTab();
    return (
        <div className="flex h-full flex-col border-l ">
            {activeFieldComponent?.id && (
                <>
                    <FieldSettings />
                </>
            )}
            {!activeFieldComponent?.id && activeSlideComponent?.id && (
                <>
                    <Tabs value={propertiesTab} onValueChange={(value) => setPropertiesTab(value as PropertiesTab)} className="h-full w-full ">
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
                            <TabsTrigger value="ai" className="w-full">
                                AI
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
                        <TabsContent value="ai" className="h-[calc(100%-60px)]">
                            <AIChatTab />
                        </TabsContent>
                    </Tabs>
                </>
            )}
        </div>
    );
}
