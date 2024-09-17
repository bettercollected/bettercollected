'use client';

import { useRouter } from 'next/navigation';

import { AnimatePresence, motion } from 'framer-motion';
import { v4 } from 'uuid';

import { FieldTypes } from '@app/models/dtos/form';
import { ButtonVariant } from '@app/models/enums/button';
import { Button } from '@app/shadcn/components/ui/button';
import { DropdownMenu, DropdownMenuContent } from '@app/shadcn/components/ui/dropdown-menu';
import { Sheet, SheetClose, SheetContent, SheetFooter, SheetTrigger } from '@app/shadcn/components/ui/sheet';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import { useAuthAtom } from '@app/store/jotai/auth';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { useCreateTemplateFromFormMutation } from '@app/store/redux/templateApi';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { NewBetterCollectedSmallLogo } from '@app/views/atoms/Icons/BetterCollectedSmallLogo';
import { LogicOutlinedIcon } from '@app/views/atoms/Icons/LogicOutlinedIcon';
import { TextareaAutosize } from '@mui/material';
import { useState } from 'react';
import PlayIcon from '../atoms/Icons/PlayIcon';
import { PlusOutlined } from '../atoms/Icons/PlusOutlined';
import { TextOutlinedIcon } from '../atoms/Icons/TextOutlined';
import InsertFieldComponent from '../molecules/Dialogs/InsertFieldModal';
import BackButton from '../molecules/FormBuilder/BackButton';
import PreviewWrapper from '../molecules/FormBuilder/PreviewWrapper';
import PublishButton from '../molecules/FormBuilder/PublishButton';
import Form from './Form/Form';

const Navbar = () => {
    const { formFields, addField } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { formState, setFormTitle } = useFormState();
    const { toast } = useToast();

    const [insertDropdownOpen, setInsertDropdownOpen] = useState(false);

    const [createTemplateFromForm, { isLoading: isCreatingTemplate }] = useCreateTemplateFromFormMutation();

    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);

    const router = useRouter();

    const { authState } = useAuthAtom();

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
                <TextareaAutosize
                    maxRows={2}
                    style={{ resize: 'none' }}
                    placeholder="Form Title"
                    value={formState.title}
                    onChange={(event) => {
                        setFormTitle(event.target.value);
                    }}
                    className="w-full overflow-clip text-ellipsis border-0"
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
                                        className="shadow-bubble border"
                                        initial={{ opacity: 0, height: '350px', overflow: 'hidden' }}
                                        animate={{ opacity: 1, height: '554px' }}
                                        exit={{ opacity: 0, height: '350px', overflow: 'hidden' }}
                                        transition={{ duration: 0.2 }}
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
                    {/* <DropdownMenu>
                    <button data-umami-event={'Add Layout Image Button'} data-umami-event-email={authState.email}>
                        <DropdownMenu.Trigger onClick={handleClickMedia}>
                            <div className={'flex items-center hover:bg-inherit'}>
                                <div className="!text-black-500 hover:!text-black-900 flex flex-row items-center gap-1 text-xs font-semibold ">
                                    <MediaOutlinedIcon />
                                    Layout Image
                                </div>
                            </div>
                        </DropdownMenu.Trigger>
                    </button>
                </DropdownMenu> */}

                    <DropdownMenu>
                        <DropdownMenu.Trigger onClick={() => {}}>
                            <div className={'flex items-center hover:bg-inherit'}>
                                <div className="!text-black-500 hover:!text-black-900 flex flex-row items-center gap-1 text-xs font-semibold ">
                                    <LogicOutlinedIcon />
                                    Logic
                                </div>
                                <span className={'bg-new-pink rounded-xl p-1 px-2 text-[10px] font-medium leading-normal text-white'}>Soon</span>
                            </div>
                        </DropdownMenu.Trigger>
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
                    <Button variant={ButtonVariant.Secondary} isLoading={isCreatingTemplate} onClick={makeTemplate}>
                        Make Template
                    </Button>
                )}

                <PublishButton />
            </div>
        </div>
    );
};
export default Navbar;
