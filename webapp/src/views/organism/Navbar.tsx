'use client';

import { useRouter } from 'next/navigation';

import { v4 } from 'uuid';

import environments from '@app/configs/environments';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FieldTypes } from '@app/models/dtos/form';
import { ButtonVariant } from '@app/models/enums/button';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { DropdownMenu } from '@app/shadcn/components/ui/dropdown-menu';
import { Sheet, SheetClose, SheetContent, SheetFooter, SheetTrigger } from '@app/shadcn/components/ui/sheet';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useActiveSlideComponent, useActiveThankYouPageComponent } from '@app/store/jotai/activeBuilderComponent';
import { useAuthAtom } from '@app/store/jotai/auth';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useNavbarState } from '@app/store/jotai/navbar';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { usePublishV2FormMutation } from '@app/store/redux/formApi';
import { useCreateTemplateFromFormMutation } from '@app/store/redux/templateApi';
import BetterCollectedSmallLogo from '@app/views/atoms/Icons/BetterCollectedSmallLogo';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { MediaOutlinedIcon } from '../atoms/Icons/MediaOutlined';
import PlayIcon from '../atoms/Icons/PlayIcon';
import { PlusOutlined } from '../atoms/Icons/PlusOutlined';
import { TextOutlinedIcon } from '../atoms/Icons/TextOutlined';
import BackButton from '../molecules/FormBuilder/BackButton';
import PreviewWrapper from '../molecules/FormBuilder/PreviewWrapper';
import Form from './Form/Form';
import { Logic } from '@app/components/icons/logic';
import { LogicOutlinedIcon } from '@app/views/atoms/Icons/LogicOutlinedIcon';

const Navbar = () => {
    const { activeSlide, formFields, addField, updateSlideImage, updateSlideLayout } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();
    const { formState, setFormTitle, updateThankYouPageLayout, updateWelcomePageLayout, updateWelcomePageImage, updateThankYouPageImage } = useFormState();
    const { navbarState, setNavbarState } = useNavbarState();
    const { toast } = useToast();

    const [publishV2Form, { isLoading }] = usePublishV2FormMutation();
    const [createTemplateFromForm, { isLoading: isCreatingTemplate }] = useCreateTemplateFromFormMutation();

    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openDialogModal } = useDialogModal();

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

    function isGreetingSlide() {
        return activeSlideComponent?.id === 'welcome-page' || activeSlideComponent?.id === 'thank-you-page';
    }

    const { resetResponderState } = useResponderState();
    const { resetFormResponseAnswer } = useFormResponse();
    const handleResetResponderState = () => {
        resetResponderState();
        resetFormResponseAnswer();
    };

    function getPageImageUpdateFunction(image: string) {
        if (image) {
            updatePagesLayout();
        }
        if (activeSlideComponent?.index === -10) {
            updateWelcomePageImage(image);
        } else if (activeSlideComponent?.index === -20) {
            updateThankYouPageImage(image);
        } else {
            updateSlideImage(image);
        }
    }

    const NO_IMAGE_LAYOUTS = [FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND, FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN];

    function updatePagesLayout() {
        if (
            (activeSlide?.properties?.layout && NO_IMAGE_LAYOUTS.includes(activeSlide?.properties?.layout)) ||
            (activeSlideComponent &&
                ((formState.welcomePage?.layout && NO_IMAGE_LAYOUTS.includes(formState.welcomePage?.layout)) ||
                    NO_IMAGE_LAYOUTS.includes(formState.thankyouPage![activeThankYouPageComponent?.index || 0]?.layout ?? FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN)))
        ) {
            if (activeSlideComponent?.index === -10) {
                updateWelcomePageLayout(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT);
            } else if (activeSlideComponent?.index === -20) {
                updateThankYouPageLayout(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT);
            } else {
                updateSlideLayout(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT);
            }
        }
    }

    const handleClickMedia = () => {
        openDialogModal('UNSPLASH_IMAGE_PICKER', {
            updatePageImage: getPageImageUpdateFunction
        });
    };

    const publishForm = async () => {
        const response: any = await publishV2Form({
            workspaceId: workspace.id,
            formId: standardForm.formId
        });
        if (response.data) {
            openDialogModal('FORM_PUBLISHED');
        }
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
        <div id="navbar" className="border-b-black-300 flex h-16 w-full justify-between border-b-[1px] bg-white p-4">
            <div className={'flex items-center gap-2'}>
                <div
                    className={'mr-4 cursor-pointer rounded-lg px-4 py-[6px] shadow'}
                    onClick={() => {
                        router.push('/' + workspace.workspaceName + '/dashboard');
                    }}
                >
                    <BetterCollectedSmallLogo />
                </div>
                <DropdownMenu>
                    <DropdownMenu.Trigger
                        className={cn(navbarState.insertClicked && 'bg-black-300', 'rounded ')}
                        onClick={() => {
                            setNavbarState({
                                ...navbarState,
                                insertClicked: true
                            });
                        }}
                    >
                        <div className={'flex items-center hover:bg-inherit'}>
                            <div className={cn('!text-black-500 hover:!text-black-900 flex flex-row items-center gap-1 text-xs font-semibold hover:bg-inherit', navbarState.insertClicked && '!text-black-900')}>
                                <PlusOutlined />
                                <span>Insert</span>
                            </div>
                        </div>
                    </DropdownMenu.Trigger>
                </DropdownMenu>

                <DropdownMenu>
                    <DropdownMenu.Trigger onClick={handleClickMedia}>
                        <div className={'flex items-center hover:bg-inherit'}>
                            <div className="!text-black-500 hover:!text-black-900 flex flex-row items-center gap-1 text-xs font-semibold ">
                                <MediaOutlinedIcon />
                                Layout Image
                            </div>
                        </div>
                    </DropdownMenu.Trigger>
                </DropdownMenu>
                <DropdownMenu>
                    <DropdownMenu.Trigger onClick={handleAddText}>
                        <div className={'flex items-center hover:bg-inherit'}>
                            <div className="!text-black-500 hover:!text-black-900 flex flex-row items-center gap-1 text-xs font-semibold ">
                                <TextOutlinedIcon />
                                <span>Text</span>
                            </div>
                        </div>
                    </DropdownMenu.Trigger>
                </DropdownMenu>
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
            <input
                type="text"
                placeholder="Form Title"
                value={formState.title}
                onChange={(event) => {
                    setFormTitle(event.target.value);
                }}
                className="border-0"
            />
            <div className={'flex items-center gap-2 '}>
                <Sheet>
                    <SheetTrigger asChild>
                        <Button icon={<PlayIcon />} variant={'v2Button'}>
                            Preview
                        </Button>
                    </SheetTrigger>
                    <SheetContent className="h-full w-full p-0" side={'bottom'} hideCloseIcon>
                        <SheetFooter>
                            <SheetClose asChild onClick={handleResetResponderState}>
                                <div className="absolute left-4 top-3  z-50 ">
                                    <BackButton />
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

                <Button isLoading={isLoading} onClick={publishForm}>
                    Publish
                </Button>
            </div>
        </div>
    );
};
export default Navbar;
