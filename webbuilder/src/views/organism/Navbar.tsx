'use client';

import { useRouter } from 'next/navigation';

import { Dashboard } from '@mui/icons-material';
import { v4 } from 'uuid';

import environments from '@app/configs/environments';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FieldTypes } from '@app/models/dtos/form';
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
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useNavbarState } from '@app/store/jotai/navbar';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import useWorkspace from '@app/store/jotai/workspace';
import { usePublishV2FormMutation } from '@app/store/redux/formApi';
import BetterCollectedSmallLogo from '@app/views/atoms/Icons/BetterCollectedSmallLogo';

import { MediaOutlinedIcon } from '../atoms/Icons/MediaOutlined';
import PlayIcon from '../atoms/Icons/PlayIcon';
import { PlusOutlined } from '../atoms/Icons/PlusOutlined';
import { TextOutlinedIcon } from '../atoms/Icons/TextOutlined';
import BackButton from '../molecules/FormBuilder/BackButton';
import PreviewWrapper from '../molecules/FormBuilder/PreviewWrapper';
import Form from './Form/Form';

const Navbar = () => {
    const { activeSlide, formFields, addField, updateSlideImage } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { formState, setFormTitle } = useFormState();
    const { navbarState, setNavbarState } = useNavbarState();
    const { toast } = useToast();

    const [publishV2Form, { isLoading }] = usePublishV2FormMutation();

    const { standardForm } = useStandardForm();
    const { workspace } = useWorkspace();
    const { openDialogModal } = useDialogModal();

    const router = useRouter();

    const handleAddText = () => {
        if (activeSlideComponent === null) {
            toast({ title: 'Add a slide to add questions', variant: 'destructive' });
            return;
        }
        if (activeSlideComponent?.index < 0) {
            toast({ title: 'Select a slide to add questions', variant: 'destructive' });
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
                            'rounded'
                        )}
                        tooltipLabel={'Insert Fields'}
                        onClick={() => {
                            isGreetingSlide()
                                ? toast({
                                      variant: 'destructive',
                                      title: 'Add Slides or Go to Slides to add fields'
                                  })
                                : setNavbarState({
                                      insertClicked: true
                                  });
                        }}
                    >
                        <div className={cn('text-xs font-semibold')}>
                            <PlusOutlined
                                color={navbarState.insertClicked ? 'black' : '#AAAAAA'}
                            />
                            <span
                                className={cn(
                                    navbarState.insertClicked && 'text-black-900'
                                )}
                            >
                                Insert
                            </span>
                        </div>
                    </DropdownMenu.Trigger>
                </DropdownMenu>
                {activeSlide &&
                    activeSlide?.properties?.layout !==
                        FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND && (
                        <DropdownMenu>
                            <DropdownMenu.Trigger
                                tooltipLabel={'Add Media'}
                                onClick={() => {
                                    openDialogModal('UNSPLASH_IMAGE_PICKER', {
                                        activeSlide,
                                        updateSlideImage
                                    });
                                }}
                            >
                                <div className="text-xs font-semibold">
                                    <MediaOutlinedIcon />
                                    Media
                                </div>
                            </DropdownMenu.Trigger>
                        </DropdownMenu>
                    )}
                <DropdownMenu>
                    <DropdownMenu.Trigger
                        tooltipLabel={'Insert Text'}
                        onClick={handleAddText}
                    >
                        <div className="text-xs font-semibold">
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
                        <Button icon={<PlayIcon />} variant={'tertiary'}>
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

                <Button
                    isLoading={isLoading}
                    onClick={async () => {
                        const response: any = await publishV2Form({
                            workspaceId: workspace.id,
                            formId: standardForm.formId
                        });
                        if (response.data) {
                                                    openDialogModal('FORM_PUBLISHED');

                            // toast({
                            //     title: 'Form Published!',
                            //     description: 'Share and start collecting responses'
                            // });
                            // router.push(
                            //     `${environments.NEXT_PUBLIC_HTTP_SCHEME}://${environments.NEXT_PUBLIC_DASHBOARD_DOMAIN}/${workspace.workspaceName}/dashboard/forms/${standardForm.formId}?view=FormLinks`
                            // );
                        }
                    }}
                >
                    Publish
                </Button>
            </div>
        </div>
    );
};
export default Navbar;
