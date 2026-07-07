import { ReactNode, useEffect, useState } from 'react';

import { useToast } from '@app/shadcn/components/ui/use-toast';
import { v4 } from 'uuid';

import { formFieldsList } from '@app/constants/form-fields';
import { FieldTypes, StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useNavbarState } from '@app/store/jotai/navbar';

const InsertFieldComponent = ({ formFields, activeSlideComponent, closeDropdown }: { formFields: any; activeSlideComponent: any; closeDropdown: () => void }) => {
    const { toast } = useToast();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { addField, addSlide, getNewField } = useFormFieldsAtom();
    const { navbarState, setNavbarState } = useNavbarState();
    const fieldId = v4();
    const authState = useAppSelector(selectAuth);

    function checkIfInputFieldExistsInSlide(slide: StandardFormFieldDto) {
        if (!slide?.properties?.fields?.length) return false;
        return slide?.properties?.fields?.some((field) => field.type && V2InputFields.includes(field.type));
    }
    const slideIndex = activeSlideComponent.index < 0 ? formFields.length - 1 : activeSlideComponent.index;
    const slide = formFields[slideIndex];

    const [currentPage, setCurrentPage] = useState(navbarState.multiplePages);
    useEffect(() => {
        const inputFieldExists = checkIfInputFieldExistsInSlide(slide);
        if (inputFieldExists) {
            setCurrentPage(!navbarState.multiplePages);
        } else {
            setCurrentPage(true);
        }
    }, []);

    const handleAddField = (field: any) => {
        const slideId = currentPage && slide !== undefined ? slide.id : v4();
        if (activeSlideComponent === null) {
            toast({ description: 'Add a slide to add fields' });
            return;
        }
        if (!currentPage || formFields.length === 0) {
            const newSlideIndex = activeSlideComponent.index < 0 ? formFields.length : activeSlideComponent.index + 1;
            addSlide(
                {
                    id: slideId,
                    index: newSlideIndex,
                    type: FieldTypes.SLIDE,
                    // Default new pages to a calm single-column layout with no
                    // decorative image. Creators opt into the image / two-column
                    // split via the Layout panel (see Design-Language.md §3).
                    properties: {
                        layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND,
                        fields: [getNewField(field, fieldId, formFields.length)]
                    }
                },
                newSlideIndex
            );
            setActiveSlideComponent({ id: slideId, index: newSlideIndex });
            window.setTimeout(function () {
                const slideElement = document.getElementById(slideId);
                slideElement?.scrollIntoView({
                    behavior: 'smooth',
                    block: 'end'
                });
            }, 500);
        } else {
            addField(getNewField(field, fieldId, slideIndex), slideIndex);
            setActiveSlideComponent({
                id: slideId,
                index: slideIndex
            });
            window.setTimeout(function () {
                const fieldElement = document.getElementById(`scroll-field-${fieldId}`);
                fieldElement?.scrollIntoView({
                    behavior: 'smooth',
                    inline: 'center'
                });
            }, 0);
        }
        setActiveFieldComponent({
            id: fieldId,
            index: (formFields[slideIndex]?.properties?.fields?.length ?? 1) - 1
        });
    };
    return (
        <div id="fields-option" className="h-[552px] w-[410px] bg-white">
            <div className="border-b-black-300 border-b p-4 text-xs font-semibold uppercase tracking-wide text-[#657085]">Insert field</div>
            <div className="border-r-black-300 w-full bg-white">
                <div className=" border-black-300 bg-new-white-200 flex w-full justify-center gap-6 border-b-[1px] p-4">
                    <div className="flex gap-2 ">
                        <input
                            type="radio"
                            id="multi-page"
                            checked={!currentPage}
                            onChange={() => { }}
                            name="multi-page"
                            className="h-5 w-5 cursor-pointer focus:ring-0 focus:ring-offset-0"
                            style={{ accentColor: '#2456CC' }}
                            onClick={(e: any) => {
                                setCurrentPage(false);
                                setNavbarState({
                                    ...navbarState,
                                    multiplePages: true
                                });
                            }}
                            value={'True'}
                        />
                        <label htmlFor="multi-page" className="p4-new text-black-700 cursor-pointer">
                            Insert in new page
                        </label>
                    </div>
                    <div className="flex gap-2">
                        <input
                            id="single-page"
                            type="radio"
                            onClick={(e: any) => {
                                setCurrentPage(true);
                                setNavbarState({
                                    ...navbarState,
                                    multiplePages: false
                                });
                            }}
                            onChange={() => { }}
                            checked={currentPage}
                            name="multi-page"
                            value={'False'}
                            className="h-5 w-5 cursor-pointer focus:ring-0 focus:ring-offset-0"
                            style={{ accentColor: '#2456CC' }}
                        />
                        <label htmlFor="single-page" className="p4-new text-black-700 cursor-pointer">
                            Insert in current page
                        </label>
                    </div>
                </div>
                <ScrollArea className="h-[462px] w-full overflow-y-auto">
                    {/* One quiet grid — white tiles, hairline borders, ink icons.
                        Selection colour (trust blue) appears only on hover/focus,
                        so it means "this is what you're about to pick". */}
                    <div className="grid w-full grid-cols-3 gap-2 p-4">
                        {Array.isArray(formFieldsList) &&
                            formFieldsList.length &&
                            formFieldsList.map(
                                (
                                    field: {
                                        name: string;
                                        type: FieldTypes;
                                        icon: ReactNode;
                                    },
                                    index: number
                                ) => {
                                    return (
                                        <button
                                            key={index}
                                            data-umami-event={'Insert Field Button'}
                                            data-umami-event-field-type={field.type}
                                            onClick={() => {
                                                closeDropdown();
                                                handleAddField(field);
                                                setNavbarState({ ...navbarState, insertClicked: true });
                                                setTimeout(() => {
                                                    setNavbarState({ ...navbarState, insertClicked: false });
                                                }, 1000);
                                            }}
                                            className="border-black-300 flex h-[96px] cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border bg-white text-[#3A465A] transition-colors hover:border-[#2456CC] hover:bg-[#F4F7FD] focus-visible:border-[#2456CC] focus-visible:outline-none"
                                        >
                                            {field.icon}
                                            <span className="text-xs font-medium">{field.name}</span>
                                        </button>
                                    );
                                }
                            )}
                    </div>
                </ScrollArea>
            </div>
        </div>
    );
};

export default InsertFieldComponent;
