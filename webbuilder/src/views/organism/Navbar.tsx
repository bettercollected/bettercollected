'use client';

import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { FieldTypes } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { DropdownMenu } from '@app/shadcn/components/ui/dropdown-menu';
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
    const { formFields, addField } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { formState, setFormTitle } = useFormState();
    const { navbarState, setNavbarState } = useNavbarState();
    const handleAddField = (field: any) => {
        if (activeSlideComponent === null) {
            toast('Add a slide to add questions');
            return;
        }

        if (activeSlideComponent?.index < 0) {
            toast('Select a slide to add questions');
            return;
        }

        const fieldId = v4();
        if (
            field.type === FieldTypes.YES_NO ||
            field.type === FieldTypes.DROP_DOWN ||
            field.type === FieldTypes.MULTIPLE_CHOICE
        ) {
            const firstChoiceId = v4();
            const secondChoiceId = v4();
            addField(
                {
                    id: fieldId,
                    index: formFields[activeSlideComponent.index]?.properties?.fields
                        ?.length
                        ? formFields[activeSlideComponent.index]?.properties?.fields
                              ?.length!
                        : 0,
                    type: field.type,
                    properties: {
                        fields: [],
                        choices: [
                            {
                                id: firstChoiceId,
                                value: field.type === FieldTypes.YES_NO ? 'Yes' : ''
                            },
                            {
                                id: secondChoiceId,
                                value: field.type === FieldTypes.YES_NO ? 'No' : ''
                            }
                        ]
                    }
                },
                activeSlideComponent?.index || 0
            );
        } else {
            addField(
                {
                    id: fieldId,
                    index: formFields[activeSlideComponent!.index]?.properties?.fields
                        ?.length
                        ? formFields[activeSlideComponent!.index]?.properties?.fields
                              ?.length!
                        : 0,
                    type: field.type
                },
                activeSlideComponent?.index || 0
            );
        }

        window.setTimeout(function () {
            document.getElementById(`input-${fieldId}`)?.focus();
        }, 0);
    };

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
                            !(
                                activeSlideComponent?.id === 'welcome-page' ||
                                activeSlideComponent?.id === 'thank-you-page'
                            ) &&
                                setNavbarState({
                                    insertClicked: true
                                });
                        }}
                    >
                        <div className="text-xs font-semibold">
                            <PlusOutlined />
                            Insert
                        </div>
                    </DropdownMenu.Trigger>
                    {/* <DropdownMenu.Content>
                        {Array.isArray(formFieldsList) &&
                            formFieldsList.map((field) => {
                                return (
                                    <DropdownMenu.Item
                                        key={field.name}
                                        onClick={() => handleAddField(field)}
                                    >
                                        {field.name}
                                    </DropdownMenu.Item>
                                );
                            })}
                    </DropdownMenu.Content> */}
                </DropdownMenu>
                <DropdownMenu>
                    <DropdownMenu.Trigger tooltipLabel={'Add Media'}>
                        <div className="text-xs font-semibold">
                            <TextOutlinedIcon />
                            Media
                        </div>
                    </DropdownMenu.Trigger>
                </DropdownMenu>
                <DropdownMenu>
                    <DropdownMenu.Trigger tooltipLabel={'Insert Text'}>
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
