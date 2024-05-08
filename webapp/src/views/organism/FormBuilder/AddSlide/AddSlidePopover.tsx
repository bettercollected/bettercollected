import { useState } from 'react';

import { Divider } from '@mui/material';
import { AnimatePresence, motion } from 'framer-motion';

import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import TemplateTab from '@app/views/organism/FormBuilder/AddSlide/TemplateTab';

import { PlusIcon } from '@app/views/atoms/Icons/PlusIcon';
import LayoutsTab from './LayoutsTab';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './AddSlideTabs';

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
                        <div className="text-black-300  hover:bg-black-200 flex h-6 w-6 items-center justify-center rounded-sm">
                            <PlusIcon className=" text-black-600 hover:text-black-800 h-5 w-5 " strokeWidth={'1.5'} />
                        </div>
                    </PopoverTrigger>
                    <PopoverContent side="right" align="start" asChild className="w-[391px] p-0">
                        {open && (
                            <motion.div key="addSlide" initial={{ opacity: 0, x: '-10%' }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2 }}>
                                <div className="!z-[1000] max-h-[640px] w-full rounded bg-white shadow-lg">
                                    <Tabs defaultValue="layout" className="h-full w-full">
                                        <TabsList className=" flex h-auto w-full gap-2 p-4">
                                            <TabsTrigger value="layout">Layout</TabsTrigger>
                                            <TabsTrigger value="template">Template</TabsTrigger>
                                        </TabsList>
                                        <Divider />
                                        <TabsContent value="layout" className="p-4 !pr-2">
                                            <LayoutsTab closePopover={closePopover} />
                                        </TabsContent>
                                        <TabsContent value="template" className="p-4">
                                            <TemplateTab closePopover={closePopover} />
                                        </TabsContent>
                                    </Tabs>
                                </div>
                            </motion.div>
                        )}
                    </PopoverContent>
                </Popover>
            </AnimatePresence>
        </div>
    );
}
