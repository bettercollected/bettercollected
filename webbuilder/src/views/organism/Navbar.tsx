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
import {
    Sheet,
    SheetClose,
    SheetContent,
    SheetFooter,
    SheetTrigger
} from '@app/shadcn/components/ui/sheet';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import {
    useActiveSlideComponent,
    useActiveThankYouPageComponent
} from '@app/store/jotai/activeBuilderComponent';
import { useAuthAtom } from '@app/store/jotai/auth';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useNavbarState } from '@app/store/jotai/navbar';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import useWorkspace from '@app/store/jotai/workspace';
import {
    useCreateTemplateFromFormMutation,
    usePublishV2FormMutation
} from '@app/store/redux/formApi';
import BetterCollectedSmallLogo from '@app/views/atoms/Icons/BetterCollectedSmallLogo';

import { MediaOutlinedIcon } from '../atoms/Icons/MediaOutlined';
import PlayIcon from '../atoms/Icons/PlayIcon';
import { PlusOutlined } from '../atoms/Icons/PlusOutlined';
import { TextOutlinedIcon } from '../atoms/Icons/TextOutlined';
import BackButton from '../molecules/FormBuilder/BackButton';
import PreviewWrapper from '../molecules/FormBuilder/PreviewWrapper';
import Form from './Form/Form';

const Navbar = () => {
    const { activeSlide, formFields, addField, updateSlideImage, updateSlideLayout } =
        useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();
    const {
        formState,
        setFormTitle,
        updateThankYouPageLayout,
        updateWelcomePageLayout,
        updateWelcomePageImage,
        updateThankYouPageImage
    } = useFormState();
    const { navbarState, setNavbarState } = useNavbarState();
    const { toast } = useToast();

    const [publishV2Form, { isLoading }] = usePublishV2FormMutation();
    const [createTemplateFromForm, { isLoading: isCreatingTemplate }] =
        useCreateTemplateFromFormMutation();

    const { standardForm } = useStandardForm();
    const { workspace } = useWorkspace();
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
                index: formFields[activeSlideComponent!.index]?.properties?.fields
                    ?.length
                    ? formFields[activeSlideComponent!.index]?.properties?.fields
                          ?.length!
                    : 0,
                type: FieldTypes.TEXT
            },
            activeSlideComponent?.index || 0
        );
        window.setTimeout(function () {
            document.getElementById(`input-${fieldId}`)?.focus();
        }, 0);
    };

    function isGreetingSlide() {
        return (
            activeSlideComponent?.id === 'welcome-page' ||
            activeSlideComponent?.id === 'thank-you-page'
        );
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

    const NO_IMAGE_LAYOUTS = [
        FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND,
        FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN
    ];

    function updatePagesLayout() {
        if (
            (activeSlide?.properties?.layout &&
                NO_IMAGE_LAYOUTS.includes(activeSlide?.properties?.layout)) ||
            (activeSlideComponent &&
                ((formState.welcomePage?.layout &&
                    NO_IMAGE_LAYOUTS.includes(formState.welcomePage?.layout)) ||
                    NO_IMAGE_LAYOUTS.includes(
                        formState.thankyouPage![activeThankYouPageComponent?.index || 0]
                            ?.layout ??
                            FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN
                    )))
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
        <div
            id="navbar"
            className="flex h-16 w-full justify-between border-b-[1px] border-b-black-300 bg-white p-4"
        >
            <div className={'flex items-center gap-2'}>
                <div
                    className={'mr-4 cursor-pointer rounded-lg px-4 py-[6px] shadow'}
                    onClick={() => {
                        router.push(
                            'https://' +
                                environments.NEXT_PUBLIC_DASHBOARD_DOMAIN +
                                '/' +
                                workspace.workspaceName +
                                '/dashboard'
                        );
                    }}
                >
                    <BetterCollectedSmallLogo />
                </div>
                <DropdownMenu>
                    <DropdownMenu.Trigger
                        className={cn(
                            navbarState.insertClicked && 'bg-black-300',
                            'rounded '
                        )}
                        onClick={() => {
                            isGreetingSlide()
                                ? toast({
                                      variant: 'default',
                                      title: 'Add Slides or Go to Slides to add fields'
                                  })
                                : setNavbarState({
                                      insertClicked: true
                                  });
                        }}
                    >
                        <div
                            className={cn(
                                'text-xs font-semibold !text-black-500 hover:bg-inherit hover:!text-black-900',
                                navbarState.insertClicked && '!text-black-900'
                            )}
                        >
                            <PlusOutlined
                            />
                            <span
                            >
                                Insert
                            </span>
                        </div>
                    </DropdownMenu.Trigger>
                </DropdownMenu>
               
                <DropdownMenu>
                    <DropdownMenu.Trigger onClick={handleClickMedia}>
                        <div className="text-xs font-semibold !text-black-500 hover:bg-inherit hover:!text-black-900 ">
                            <MediaOutlinedIcon />
                            Media
                        </div>
                    </DropdownMenu.Trigger>
                </DropdownMenu>
                <DropdownMenu>
                    <DropdownMenu.Trigger onClick={handleAddText}>
                        <div className="text-xs font-semibold !text-black-500 hover:bg-inherit hover:!text-black-900">
                            <TextOutlinedIcon />
                            Text
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
                    <SheetContent
                        className="h-full w-full p-0"
                        side={'bottom'}
                        hideCloseIcon
                    >
                        <SheetFooter>
                            <SheetClose asChild onClick={handleResetResponderState}>
                                <div className="absolute left-4  z-50 ">
                                    <BackButton />
                                </div>
                            </SheetClose>
                        </SheetFooter>
                        <PreviewWrapper
                            handleResetResponderState={handleResetResponderState}
                        >
                            <Form isPreviewMode />
                        </PreviewWrapper>
                    </SheetContent>
                </Sheet>
                {authState?.roles?.includes('ADMIN') && (
                    <Button
                        variant={ButtonVariant.Secondary}
                        isLoading={isCreatingTemplate}
                        onClick={makeTemplate}
                    >
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
