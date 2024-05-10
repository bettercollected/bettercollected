'use client';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@app/shadcn/components/ui/tabs';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import FieldSettings from '@app/views/organism/FieldSettings';
import PageDesignTab from '@app/views/organism/FormBuilder/PageDesignTab';
import PagePropertiesTab from '@app/views/organism/FormBuilder/PagePropertiesTab';

export default function PropertiesDrawer({}: {}) {
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
