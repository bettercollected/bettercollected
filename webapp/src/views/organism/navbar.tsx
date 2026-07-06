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
import { useNavbarState } from '@app/store/jotai/navbar';
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
import { slideHasLogic } from '@app/utils/conditional-logic';
import { PlayIcon, Redo2, Undo2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import InsertFieldComponent from '../molecules/dialogs/insert-field-modal';
import BackButton from '../molecules/form-builder/back-button';

// Code-split: React Flow only loads when the Flow view is opened.
const FlowView = dynamic(() => import('./form-builder/flow-view'), { ssr: false });
import PreviewWrapper from '../molecules/form-builder/preview-wrapper';
import PublishButton from '../molecules/form-builder/publish-button';
import Form from './form/form';

const Navbar = () => {
    const { formFields, addField, undo, redo, canUndo, canRedo } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { formState, setFormTitle } = useFormState();
    const { toast } = useToast();
    const { navbarState, setNavbarState } = useNavbarState();

    // In jotai (navbarState) so the empty-canvas "Add a question" affordance
    // can open the same menu (see slide-builder.tsx).
    const insertDropdownOpen = !!navbarState.insertMenuOpen;
    const setInsertDropdownOpen = (open: boolean) => setNavbarState({ ...navbarState, insertMenuOpen: open });
    const [flowViewOpen, setFlowViewOpen] = useState(false);

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

    // Default-view heuristic: forms that already branch open in the Flow view
    // (once per form — closing it remembers the preference in localStorage).
    const flowAutoOpened = useRef(false);
    useEffect(() => {
        const formId = standardForm?.formId;
        if (!formId || flowAutoOpened.current) return;
        // Defensive: the atom can transiently hold non-array state (e.g. a stale
        // reset from another route) before this editor re-initializes it.
        if (!Array.isArray(formFields) || !formFields.some((slide) => slideHasLogic(slide))) return;
        if (localStorage.getItem(`bc-default-view-${formId}`)) return;
        flowAutoOpened.current = true;
        setFlowViewOpen(true);
    }, [standardForm?.formId, formFields]);

    const handleFlowViewOpenChange = (open: boolean) => {
        setFlowViewOpen(open);
        // Closing counts as choosing the page view; don't auto-open this form again.
        if (!open && standardForm?.formId) localStorage.setItem(`bc-default-view-${standardForm.formId}`, 'page');
    };

    // Builder-wide undo/redo shortcuts. Text inputs and the Tiptap title editors
    // keep their own native/undo handling — we only act when focus is elsewhere.
    useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            const target = e.target as HTMLElement | null;
            if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
            if (!(e.ctrlKey || e.metaKey)) return;
            const key = e.key.toLowerCase();
            if (key === 'z' && !e.shiftKey) {
                e.preventDefault();
                undo();
            } else if (key === 'y' || (key === 'z' && e.shiftKey)) {
                e.preventDefault();
                redo();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    });

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

                    <button data-umami-event={'Open Flow View'} data-umami-event-email={authState.email} onClick={() => setFlowViewOpen(true)}>
                        <div className={'flex items-center hover:bg-inherit'}>
                            <div className="!text-black-500 hover:!text-black-900 flex flex-row items-center gap-1 text-xs font-semibold ">
                                <LogicOutlinedIcon />
                                Logic
                            </div>
                        </div>
                    </button>
                </div>
            )}

            <div className={'flex flex-1 items-center justify-end  gap-2'}>
                <div className="mr-1 flex items-center gap-1">
                    <button aria-label="Undo" title="Undo (Ctrl+Z)" disabled={!canUndo} onClick={undo} className="text-black-600 hover:text-black-900 rounded-md p-1.5 hover:bg-black-100 disabled:opacity-30 disabled:hover:bg-transparent">
                        <Undo2 className="h-4 w-4" />
                    </button>
                    <button aria-label="Redo" title="Redo (Ctrl+Shift+Z)" disabled={!canRedo} onClick={redo} className="text-black-600 hover:text-black-900 rounded-md p-1.5 hover:bg-black-100 disabled:opacity-30 disabled:hover:bg-transparent">
                        <Redo2 className="h-4 w-4" />
                    </button>
                </div>
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

            {/* Flow view — mounted at the navbar root so the default-view heuristic
                can open it regardless of which page (if any) is active. */}
            <Sheet open={flowViewOpen} onOpenChange={handleFlowViewOpenChange}>
                <SheetContent className="h-full w-full p-0" side={'bottom'} hideCloseIcon>
                    <SheetTitle className="sr-only">Flow view</SheetTitle>
                    <FlowView onClose={() => handleFlowViewOpenChange(false)} />
                </SheetContent>
            </Sheet>
        </div>
    );
};
export default Navbar;
