import { ReactNode, useEffect, useState } from 'react';

import { motion } from 'framer-motion';
import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { formFieldsList } from '@app/constants/form-fields';
import { FieldTypes, StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useNavbarState } from '@app/store/jotai/navbar';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';

const InsertFieldComponent = ({ formFields, activeSlideComponent }: { formFields: any; activeSlideComponent: any }) => {
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { addField, addSlide, getNewField } = useFormFieldsAtom();
    const { navbarState, setNavbarState } = useNavbarState();
    const fieldId = v4();
    const { closeDialogModal } = useDialogModal();

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
            console.log('inputfields', currentPage, navbarState.multiplePages);
        } else {
            setCurrentPage(true);
            console.log('no', currentPage, navbarState.multiplePages);
        }
    }, []);

    const handleAddField = (field: any) => {
        const slideId = !currentPage ? v4() : slide.id;
        if (activeSlideComponent === null) {
            toast('Add a slide to add fields');
            return;
        }
        if (!currentPage || formFields.length === 0) {
            addSlide({
                id: slideId,
                index: formFields.length,
                type: FieldTypes.SLIDE,
                properties: {
                    layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
                    fields: [getNewField(field, fieldId, formFields.length)]
                },
                imageUrl: 'https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2defaultImage.png'
            });
            setActiveSlideComponent({ id: slideId, index: formFields.length });
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
                    block: 'end'
                });
            }, 500);
        }
        setNavbarState({ ...navbarState, insertClicked: false });
        setActiveFieldComponent({
            id: fieldId,
            index: (formFields[slideIndex]?.properties?.fields?.length ?? 1) - 1
        });
        closeDialogModal();
    };
    return (
        <div id="fields-option" className="w-full">
            <div className="border-b-black-300 text-black-700 border-b p-4 text-xs">Insert Field</div>
            <div className="border-r-black-300 w-full bg-white">
                <div className=" border-black-300 bg-new-white-200 flex w-full justify-center gap-6 border-b-[1px] p-4">
                    <div className="flex gap-2 ">
                        <input
                            type="radio"
                            id="multi-page"
                            checked={!currentPage}
                            onChange={() => {}}
                            name="multi-page"
                            className="h-5 w-5 cursor-pointer focus:ring-0 focus:ring-offset-0"
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
                            onChange={() => {}}
                            checked={currentPage}
                            name="multi-page"
                            value={'False'}
                            className="h-5 w-5 cursor-pointer focus:ring-0 focus:ring-offset-0"
                        />
                        <label htmlFor="single-page" className="p4-new text-black-700 cursor-pointer">
                            Insert in current page
                        </label>
                    </div>
                </div>
                <ScrollArea className="h-full  overflow-y-auto  overflow-x-hidden p-6 md:h-[600px]">
                    <div className="flex h-full w-full flex-wrap justify-start gap-[1px]">
                        {Array.isArray(formFieldsList) &&
                            formFieldsList.length &&
                            formFieldsList.map(
                                (
                                    field: {
                                        name: string;
                                        type: FieldTypes;
                                        icon: ReactNode;
                                        background: string;
                                    },
                                    index: number
                                ) => {
                                    return (
                                        <div
                                            onClick={() => handleAddField(field)}
                                            key={index}
                                            style={{ background: field.background }}
                                            className="text-black-600 hover:text-black-900 flex h-[100px] w-[100px] cursor-grab flex-col items-center justify-center gap-2 hover:saturate-200 md:h-[120px] md:w-[120px] "
                                        >
                                            {field.icon}
                                            <span className="text-xs"> {field.name}</span>
                                        </div>
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
