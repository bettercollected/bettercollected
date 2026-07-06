'use client';

import { useRouter } from 'next/navigation';

import { AnimatePresence, motion } from 'framer-motion';
import { v4 } from 'uuid';

import { FieldTypes } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { DropdownMenu, DropdownMenuContent } from '@app/shadcn/components/ui/dropdown-menu';
import { Sheet, SheetClose, SheetContent, SheetTitle, SheetFooter, SheetTrigger } from '@app/shadcn/components/ui/sheet';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useCreateTemplateFromFormMutation } from '@app/store/redux/template-api';

import { AppInput } from '@app/shadcn/components/ui/input';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { NewBetterCollectedSmallLogo } from '@Components/icons/bettercollected-small-logo';
import { LogicOutlinedIcon } from '@Components/icons/logic-outlined-icon';
import { PlusOutlined } from '@Components/icons/plus-outlined';
import { TextOutlinedIcon } from '@Components/icons/text-outlined';
import { PlayIcon } from 'lucide-react';
import { useState } from 'react';
import InsertFieldComponent from '../molecules/dialogs/insert-field-modal';
import LogicOverview from '../molecules/form-builder/logic-overview';
import BackButton from '../molecules/form-builder/back-button';
import PreviewWrapper from '../molecules/form-builder/preview-wrapper';
import PublishButton from '../molecules/form-builder/publish-button';
import Form from './form/form';

const Navbar = () => {
    const { formFields, addField } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { formState, setFormTitle } = useFormState();
    const { toast } = useToast();

    const [insertDropdownOpen, setInsertDropdownOpen] = useState(false);
    const [logicDropdownOpen, setLogicDropdownOpen] = useState(false);

    const [createTemplateFromForm, { isLoading: isCreatingTemplate }] = useCreateTemplateFromFormMutation();

    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);

    const router = useRouter();

    const authState = useAppSelector(selectAuth);

    const handleAddText = () => {
        if (activeSlideComponent === null) {
            toast({ title: 'Add a slide to add questions', variant: 'default' });
            return;
        }
        if (activeSlideComponent?.index < 0) {
            toast({ title: 'Select a slide to add questions', variant: 'default' });
            return;
        }

        const fieldId = v4();
        addField(
            {
                id: fieldId,
                index: formFields[activeSlideComponent!.index]?.properties?.fields?.length ? formFields[activeSlideComponent!.index]?.properties?.fields?.length! : 0,
                type: FieldTypes.TEXT
            },
            activeSlideComponent?.index || 0
        );
        window.setTimeout(function () {
            const element = document.getElementById(`scroll-field-${fieldId}`);
            element?.scrollIntoView({
                behavior: 'smooth',
                block: 'end'
            });
        }, 0);
    };

    const { resetResponderState } = useResponderState();
    const { resetFormResponseAnswer } = useFormResponse();
    const handleResetResponderState = () => {
        resetResponderState();
        resetFormResponseAnswer();
    };

    const makeTemplate = async () => {
        const response: any = await createTemplateFromForm({
            form_id: standardForm.formId,
            workspace_id: workspace.id
        });
        if (response?.data) {
            toast({ title: 'Temaplate Created', variant: 'default' });
        }
    };

    return (
        <div id="navbar" className="border-b-black-300 flex h-16 w-full justify-between border-b-[1px] p-4">
            <div className={'flex flex-1 items-center gap-[2px]'}>
                <div
                    className={'bg-brand-500 active:bg-brand-600 cursor-pointer rounded-[5px] p-[6px] text-white shadow'}
                    onClick={() => {
                        router.push('/' + workspace.workspaceName + '/dashboard/forms');
                    }}
                >
                    <NewBetterCollectedSmallLogo width={17} height={19} />
                </div>
                <AppInput
                    placeholder="Form Title"
                    value={formState.title}
                    onChange={(event) => {
                        console.log("Changed title to ", event.target.value);
                        setFormTitle(event.target.value);
                    }}
                    className="w-full overflow-clip text-ellipsis border-0 resize-none"
                />
            </div>
            {activeSlideComponent && activeSlideComponent.index >= 0 && (
                <div className={'flex min-w-fit flex-1 items-center justify-center gap-2'}>
                    <DropdownMenu
                        open={insertDropdownOpen}
                        onOpenChange={(open) => {
                            setInsertDropdownOpen(open);
                        }}
                    >
                        <DropdownMenu.Trigger>
                            <div className={'flex items-center hover:bg-inherit'}>
                                <div className="!text-black-500 hover:!text-black-900 flex flex-row items-center gap-1 text-xs font-semibold ">
                                    <PlusOutlined />
                                    <span>Insert</span>
                                </div>
                            </div>
                        </DropdownMenu.Trigger>
                        <AnimatePresence key="insert-dropdown" initial={false} mode="wait">
                            {insertDropdownOpen && (
                                <DropdownMenuContent key="insert-dropdown" className=" w-[410px] border-none p-0">
                                    <motion.div
                                        key="insert-dropdown"
                                        {...({
                                            className: 'shadow-bubble border',
                                            initial: { opacity: 0, height: '350px', overflow: 'hidden' },
                                            animate: { opacity: 1, height: '554px' },
                                            exit: { opacity: 0, height: '350px', overflow: 'hidden' },
                                            transition: { duration: 0.2 }
                                        } as any)}
                                    >
                                        <InsertFieldComponent
                                            formFields={formFields}
                                            activeSlideComponent={activeSlideComponent}
                                            closeDropdown={() => {
                                                setInsertDropdownOpen(false);
                                            }}
                                        />
                                    </motion.div>
                                </DropdownMenuContent>
                            )}
                        </AnimatePresence>
                    </DropdownMenu>
                    <DropdownMenu>
                        <button data-umami-event={'Add Heading Button'} data-umami-event-email={authState.email}>
                            <DropdownMenu.Trigger onClick={handleAddText}>
                                <div className={'flex items-center hover:bg-inherit'}>
                                    <div className="!text-black-500 hover:!text-black-900 flex flex-row items-center gap-1 text-xs font-semibold ">
                                        <TextOutlinedIcon />
                                        <span>Text</span>
                                    </div>
                                </div>
                            </DropdownMenu.Trigger>
                        </button>
                    </DropdownMenu>

                    <DropdownMenu open={logicDropdownOpen} onOpenChange={setLogicDropdownOpen}>
                        <DropdownMenu.Trigger>
                            <div className={'flex items-center hover:bg-inherit'}>
                                <div className="!text-black-500 hover:!text-black-900 flex flex-row items-center gap-1 text-xs font-semibold ">
                                    <LogicOutlinedIcon />
                                    Logic
                                </div>
                            </div>
                        </DropdownMenu.Trigger>
                        <AnimatePresence key="logic-dropdown" initial={false} mode="wait">
                            {logicDropdownOpen && (
                                <DropdownMenuContent key="logic-dropdown" className="border-none bg-transparent p-0 shadow-none">
                                    <LogicOverview onClose={() => setLogicDropdownOpen(false)} />
                                </DropdownMenuContent>
                            )}
                        </AnimatePresence>
                    </DropdownMenu>
                </div>
            )}

            <div className={'flex flex-1 items-center justify-end  gap-2'}>
                <Sheet>
                    <SheetTrigger asChild>
                        <Button icon={<PlayIcon />} variant={'v2Button'} data-umami-event={`Preview Button`} data-umami-event-email={authState.email}>
                            Preview
                        </Button>
                    </SheetTrigger>
                    <SheetContent className="h-full w-full p-0" side={'bottom'} hideCloseIcon>
                        <SheetTitle className="sr-only">Navigation menu</SheetTitle>
                        <SheetFooter>
                            <SheetClose asChild onClick={handleResetResponderState}>
                                <div className="absolute left-4 top-16 z-50 lg:top-3 ">
                                    <BackButton hideForSmallScreen />
                                </div>
                            </SheetClose>
                        </SheetFooter>
                        <PreviewWrapper handleResetResponderState={handleResetResponderState}>
                            <Form isPreviewMode />
                        </PreviewWrapper>
                    </SheetContent>
                </Sheet>
                {authState?.roles?.includes('ADMIN') && (
                    <Button variant="secondary" isLoading={isCreatingTemplate} onClick={makeTemplate}>
                        Make Template
                    </Button>
                )}

                <PublishButton />
            </div>
        </div>
    );
};
export default Navbar;
