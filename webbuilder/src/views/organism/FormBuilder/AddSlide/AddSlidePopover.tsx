import { useState } from 'react';

import { Divider } from '@mui/material';
import { AnimatePresence, motion } from 'framer-motion';

import { ButtonSize, ButtonVariant } from '@app/models/enums/button';
import { Button } from '@app/shadcn/components/ui/button';
import {
    Popover,
    PopoverContent,
    PopoverTrigger
} from '@app/shadcn/components/ui/popover';
import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger
} from '@app/shadcn/components/ui/tabs';

import LayoutsTab from './LayoutsTab';

export default function AddSlidePopover() {
    const [open, setOpen] = useState(false);

    const closePopover = () => {
        setOpen(false);
    };

    return (
        <div className="z-10">
            <AnimatePresence key="add_slide" mode="wait">
                <Popover
                    open={open}
                    onOpenChange={(open) => {
                        setOpen(open);
                    }}
                >
                    <PopoverTrigger>
                        <Button
                            variant={ButtonVariant.Ghost}
                            className="!p-2"
                            size={ButtonSize.Small}
                        >
                            Add Slide
                        </Button>
                    </PopoverTrigger>
                    {open && (
                        <motion.div
                            className="!z-10"
                            key="addSlide"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                        >
                            <PopoverContent
                                side="right"
                                align="start"
                                asChild
                                className="p-0"
                            >
                                <div className="!z-[1000] w-[384px] rounded-lg bg-white shadow-lg">
                                    <Tabs
                                        defaultValue="layout"
                                        className="h-full w-full"
                                    >
                                        <TabsList className=" flex h-auto w-full gap-2 p-4">
                                            <TabsTrigger
                                                value="layout"
                                                className="w-full"
                                            >
                                                Layout
                                            </TabsTrigger>
                                            <TabsTrigger
                                                value="template"
                                                className="w-full"
                                            >
                                                Template
                                            </TabsTrigger>
                                            <TabsTrigger
                                                value="pages"
                                                className="w-full"
                                            >
                                                Pages
                                            </TabsTrigger>
                                        </TabsList>
                                        <Divider />
                                        <TabsContent value="layout" className="p-4">
                                            <LayoutsTab closePopover={closePopover} />
                                        </TabsContent>
                                        <TabsContent value="template" className="p-4">
                                            This will be Template Tab
                                        </TabsContent>
                                        <TabsContent value="pages" className="p-4">
                                            This will be Pages Tab
                                        </TabsContent>
                                    </Tabs>
                                </div>
                            </PopoverContent>
                        </motion.div>
                    )}
                </Popover>
            </AnimatePresence>
        </div>
    );
}