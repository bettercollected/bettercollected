import { useState } from 'react';

import { Separator } from '@app/shadcn/components/ui/separator';
import { AnimatePresence, motion } from 'framer-motion';

import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import TemplateTab from '@app/views/organism/form-builder/add-slide/template-tab';

import { PlusIcon } from '@Components/icons/plus-icon';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './add-slice-tabs';
import LayoutsTab from './layouts-tab';

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
                            <motion.div
                                {...({
                                    key: 'addSlide',
                                    initial: { opacity: 0, x: '-10%' },
                                    animate: { opacity: 1, x: 0 },
                                    transition: { duration: 0.2 }
                                } as any)}
                            >
                                <div className="!z-[1000] max-h-[640px] w-full rounded bg-white shadow-lg">
                                    <Tabs defaultValue="layout" className="h-full w-full">
                                        <TabsList className=" flex h-auto w-full gap-2 p-4">
                                            <TabsTrigger value="layout">Layout</TabsTrigger>
                                            <TabsTrigger value="template">Template</TabsTrigger>
                                        </TabsList>
                                        <Separator />
                                        <TabsContent value="layout" className="p-4 !pr-0">
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
