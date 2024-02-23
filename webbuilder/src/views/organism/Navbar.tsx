'use client';

import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { formFieldsList } from '@app/constants/form-fields';
import { FieldTypes } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { DropdownMenu } from '@app/shadcn/components/ui/dropdown-menu';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFieldSelectorAtom from '@app/store/jotai/fieldSelector';
import BetterCollectedSmallLogo from '@app/views/atoms/Icons/BetterCollectedSmallLogo';
import EllipsisOption from '@app/views/atoms/Icons/EllipsisOption';

import PlayIcon from '../atoms/Icons/PlayIcon';

const Navbar = () => {
    const { formFields, addField } = useFieldSelectorAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const handleAddField = (field: any) => {
        if (activeSlideComponent === null) {
            toast('Add a slide to add questions');
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
            <div className={'flex items-center gap-2'}>
                <div className={'mr-4 rounded-lg px-4 py-[6px] shadow'}>
                    <BetterCollectedSmallLogo />
                </div>
                <input
                    type="text"
                    placeholder="Fill the Form Title"
                    className="w-1/2 border-0"
                />
                <EllipsisOption />
            </div>
            <div className={'flex items-center gap-4'}>
                <DropdownMenu>
                    <DropdownMenu.Trigger tooltipLabel={'Insert Fields'}>
                        <div>
                            <div className={'h-6 w-6 rounded bg-black-400'}></div>
                            Insert
                        </div>
                    </DropdownMenu.Trigger>
                    <DropdownMenu.Content>
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
                    </DropdownMenu.Content>
                </DropdownMenu>
                <DropdownMenu>
                    <DropdownMenu.Trigger tooltipLabel={'Add Media'}>
                        <div>
                            <div className={'h-6 w-6 rounded bg-black-400'}></div>
                            Media
                        </div>
                    </DropdownMenu.Trigger>
                </DropdownMenu>
                <DropdownMenu>
                    <DropdownMenu.Trigger tooltipLabel={'Insert Text'}>
                        <div>
                            <div className={'h-6 w-6 rounded bg-black-400'}></div>
                            Text
                        </div>
                    </DropdownMenu.Trigger>
                </DropdownMenu>
            </div>
            <div className={'flex items-center gap-2'}>
                <Button icon={<PlayIcon />} variant={'tertiary'}>
                    Preview
                </Button>
                <Button>Publish</Button>
            </div>
        </div>
    );
};
export default Navbar;
