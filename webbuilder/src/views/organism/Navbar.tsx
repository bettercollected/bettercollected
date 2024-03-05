'use client';

import Image from 'next/image';

import { v4 } from 'uuid';

import { templates } from '@app/app/[workspaceName]/dashboard/forms/create/page';
import { FieldTypes } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { DropdownMenu } from '@app/shadcn/components/ui/dropdown-menu';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useNavbarState } from '@app/store/jotai/navbar';
import BetterCollectedSmallLogo from '@app/views/atoms/Icons/BetterCollectedSmallLogo';

import { MediaOutlinedIcon } from '../atoms/Icons/MediaOutlined';
import PlayIcon from '../atoms/Icons/PlayIcon';
import { PlusOutlined } from '../atoms/Icons/PlusOutlined';
import { TextOutlinedIcon } from '../atoms/Icons/TextOutlined';

const Navbar = () => {
    const { formFields, addField, addMedia } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { formState, setFormTitle } = useFormState();
    const { navbarState, setNavbarState } = useNavbarState();
    const { toast } = useToast();

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

    const handleAddMedia = (imageUrl: string) => {
        addMedia(activeSlideComponent?.index || 0, imageUrl);
    };

    function isGreetingSlide() {
        return (
            activeSlideComponent?.id === 'welcome-page' ||
            activeSlideComponent?.id === 'thank-you-page'
        );
    }

    return (
        <div
            id="navbar"
            className="flex h-16 w-full justify-between border-b-[1px] border-b-black-300 bg-white p-4"
        >
            <div className={'flex items-center gap-6'}>
                <div className={'mr-4 rounded-lg px-4 py-[6px] shadow'}>
                    <BetterCollectedSmallLogo />
                </div>
                <DropdownMenu>
                    <DropdownMenu.Trigger
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
                        <div className="text-xs font-semibold">
                            <PlusOutlined />
                            Insert
                        </div>
                    </DropdownMenu.Trigger>
                </DropdownMenu>
                <DropdownMenu>
                    <DropdownMenu.Trigger tooltipLabel={'Add Media'}>
                        <div className="text-xs font-semibold">
                            <TextOutlinedIcon />
                            Media
                        </div>
                    </DropdownMenu.Trigger>
                    <DropdownMenu.Content>
                        <DropdownMenu.Item>
                            <div className="grid grid-cols-1 gap-x-6 gap-y-10 px-2 sm:grid-cols-2 lg:grid-cols-3">
                                {templates.map(
                                    (template: { imageUrl: string; title: string }) => (
                                        <div
                                            className="flex cursor-pointer flex-col"
                                            key={template.imageUrl}
                                            onClick={() =>
                                                handleAddMedia(template.imageUrl)
                                            }
                                        >
                                            <div className="relative !aspect-video overflow-hidden rounded-md">
                                                <Image
                                                    alt={template.title}
                                                    src={template.imageUrl}
                                                    fill
                                                    sizes="100%"
                                                    style={{ objectFit: 'cover' }}
                                                />
                                            </div>
                                            <div className="p2-new mt-2 !font-medium">
                                                {template.title}
                                            </div>
                                        </div>
                                    )
                                )}
                            </div>
                        </DropdownMenu.Item>
                    </DropdownMenu.Content>
                </DropdownMenu>
                <DropdownMenu>
                    <DropdownMenu.Trigger
                        tooltipLabel={'Insert Text'}
                        onClick={handleAddText}
                    >
                        <div className="text-xs font-semibold">
                            <MediaOutlinedIcon />
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
                <Button icon={<PlayIcon />} variant={'tertiary'}>
                    Preview
                </Button>
                <Button>Publish</Button>
            </div>
        </div>
    );
};
export default Navbar;
