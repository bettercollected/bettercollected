'use client';

import { JSONContent } from '@tiptap/react';
import { atom, useAtom } from 'jotai';
import { v4 } from 'uuid';

import globalConstants from '@app/constants/global';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import { reorder } from '@app/utils/arrayUtils';

const initialFieldsAtom = atom<StandardFormFieldDto[]>([
    {
        id: v4(),
        index: 0,
        type: FieldTypes.SLIDE,
        properties: {
            layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
            fields: [
                {
                    id: v4(),
                    index: 0,
                    type: FieldTypes.SHORT_TEXT,
                    value: 'Hi, what is your name?',
                    properties: {
                        placeholder: 'Answer'
                    }
                }
            ]
        },
        imageUrl: globalConstants.defaultImage
    }
]);

export default function useFormFieldsAtom() {
    const [formFields, setFormFields] = useAtom(initialFieldsAtom);

    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent, setActiveFieldComponent } = useActiveFieldComponent();

    const addSlide = (field: StandardFormFieldDto, index: number) => {
        formFields.splice(index, 0, field);
        formFields.map((slide, index: number) => {
            slide.index = index;
            return slide;
        });
        setFormFields([...formFields]);
    };

    const addSlideFormTemplate = (slide: StandardFormFieldDto, index?: number) => {
        const formSlide = {
            ...slide,
            id: v4()
        };
        let spliceIndex;
        if ((activeSlideComponent?.index || activeSlideComponent?.index === 0) && activeSlideComponent?.index >= 0) {
            spliceIndex = activeSlideComponent?.index + 1;
        } else {
            spliceIndex = formFields.length;
        }
        const updatedSlide = {
            ...formSlide,
            properties: {
                ...formSlide.properties,
                fields: [...(formSlide?.properties?.fields || [])].map((field) => ({
                    ...field,
                    id: v4()
                }))
            }
        };
        formFields.splice(spliceIndex, 0, { ...updatedSlide });

        const updatedFormFields = formFields.map((field, index) => ({
            ...field,
            index: index
        }));
        setFormFields([...updatedFormFields]);
        setActiveSlideComponent({ index: spliceIndex, id: formSlide.id });
        window.setTimeout(function () {
            const element = document.getElementById(formSlide.id);
            element?.scrollIntoView({
                behavior: 'smooth',
                block: 'end'
            });
        }, 500);
    };

    const deleteSlide = (slideIndex: number) => {
        formFields.splice(slideIndex, 1);
        const updatedFormFields = formFields?.map((slide: StandardFormFieldDto, index) => {
            slide.index = index;
            return slide;
        });
        if (activeSlideComponent?.index === formFields.length) {
            setActiveSlideComponent({
                id: 'welcome-page',
                index: -10
            });
        }
        setFormFields([...updatedFormFields]);
    };

    const getActiveSlide = () => {
        if (activeSlideComponent?.index !== undefined) return formFields[activeSlideComponent!.index];
        return;
    };

    const activeSlide = getActiveSlide();

    const getActiveField = () => {
        if (activeFieldComponent?.index !== undefined) return activeSlide?.properties?.fields![activeFieldComponent.index];
        return;
    };
    const activeField = getActiveField();

    const addField = (slideField: StandardFormFieldDto, slideIndex: number) => {
        const slide = formFields[slideIndex];
        slide?.properties?.fields!.push(slideField);
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateTitle = (fieldIndex: number, slideIndex: number, titleText: JSONContent) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex] = {
            ...(slide.properties!.fields![fieldIndex] || {}),
            title: titleText
        };
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const addMedia = (slideIndex: number, imageUrl: string) => {
        formFields[slideIndex].imageUrl = imageUrl;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateFieldImage = (imageUrl: string) => {
        formFields[activeSlide?.index || 0]!.properties!.fields![activeField?.index || 0]!.imageUrl = imageUrl;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateDescription = (fieldIndex: number, slideIndex: number, description: string | undefined) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex].description = description;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateFieldPlaceholder = (fieldIndex: number, slideIndex: number, placeholderText: string) => {
        const existingSlide = formFields[slideIndex];
        const slide = { ...existingSlide };
        slide.properties!.fields![fieldIndex]['properties'] = { ...(slide.properties!.fields![fieldIndex].properties || { fields: [] }) };
        slide.properties!.fields![fieldIndex]!.properties!.placeholder = placeholderText;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateChoiceFieldValue = (fieldIndex: number, slideIndex: number, choiceId: string, choiceValue: string) => {
        const existingSlide = formFields[slideIndex];
        const slide = { ...existingSlide };
        slide.properties!.fields![fieldIndex]['properties'] = { ...(slide.properties!.fields![fieldIndex].properties || { fields: [] }) };
        slide.properties!.fields![fieldIndex]!.properties!.choices = slide.properties!.fields![fieldIndex]?.properties?.choices?.map((choice) => {
            if (choice.id === choiceId) {
                const existingChoice = { ...choice };
                existingChoice.value = choiceValue;
                return existingChoice;
            } else return choice;
        });
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const addChoiceField = (fieldIndex: number, slideIndex: number) => {
        const choiceId = v4();
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex]?.properties?.choices?.push({
            id: choiceId
        });
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const removeChoiceField = (fieldIndex: number, slideIndex: number, choiceId: string) => {
        const field = formFields[slideIndex].properties!.fields![fieldIndex];
        field.properties && (field.properties.choices = field?.properties?.choices?.filter((choice) => choice.id != choiceId));
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateFieldRequired = (fieldIndex: number, slideIndex: number, required: boolean) => {
        formFields[slideIndex].properties!.fields![fieldIndex].validations = {
            ...formFields[slideIndex].properties!.fields![fieldIndex].validations,
            required: required
        };
        setFormFields([...formFields]);
    };

    const updateFieldValidation = (fieldIndex: number, slideIndex: number, validation: any) => {
        formFields[slideIndex].properties!.fields![fieldIndex].validations = {
            ...formFields[slideIndex].properties!.fields![fieldIndex].validations,
            ...validation
        };
        setFormFields([...formFields]);
    };

    const updateShowQuestionNumbers = (slideIndex: number, show: boolean) => {
        formFields![slideIndex]!.properties = {
            ...(formFields[slideIndex].properties || {}),
            showQuestionNumbers: show
        };
        setFormFields([...formFields]);
    };

    const updateSlideTheme = (color: { title: string; primary: string; secondary: string; tertiary: string; accent: string }) => {
        formFields[activeSlide?.index || 0].properties!.theme = {
            title: color.title,
            primary: color.primary,
            secondary: color.secondary,
            tertiary: color.tertiary,
            accent: color.accent
        };
        setFormFields([...formFields]);
    };

    const updateSlideLayout = (layout: FormSlideLayout) => {
        formFields[activeSlide?.index || 0].properties!.layout = layout;
        setFormFields([...formFields]);
    };

    const updateSlideImage = (imageUrl: string) => {
        formFields[activeSlide?.index || 0].imageUrl = imageUrl;
        setFormFields([...formFields]);
    };

    const moveFieldInASlide = (slideIndex: number, sourceIndex: number, destinationIndex: number) => {
        if (destinationIndex < 0 || (activeSlide?.properties?.fields?.length || -1) < destinationIndex) return;
        formFields![slideIndex]!.properties!.fields = reorder(formFields![slideIndex]!.properties!.fields!, sourceIndex, destinationIndex);
        setFormFields([...formFields]);
        setTimeout(() => {
            setActiveFieldComponent({ index: destinationIndex, id: activeFieldComponent!.id });
        }, 0);
    };

    const updateFieldProperty = (fieldIndex: number, slideIndex: number, property: string, value: any) => {
        formFields![slideIndex]!.properties!.fields![fieldIndex].properties = {
            ...(formFields![slideIndex]!.properties!.fields![fieldIndex].properties || {}),
            [property]: value
        };
        setFormFields([...formFields]);
    };

    const deleteField = (slideIndex: number, fieldIndex: number) => {
        formFields![slideIndex]!.properties!.fields!.splice(fieldIndex, 1);
        formFields![slideIndex!].properties!.fields = formFields![slideIndex!].properties!.fields?.map((field, index) => ({
            ...field,
            index
        }));
        setFormFields([...formFields]);
        setTimeout(() => {
            setActiveFieldComponent(null);
        }, 0);
    };

    const deleteActiveSlide = () => {
        const slideIndex = getActiveSlide()?.index;
        formFields.splice(slideIndex!, 1);

        formFields.forEach((field, index) => {
            field.index = index;
        });

        const newActiveSlideIndex = slideIndex! - 1;
        if (newActiveSlideIndex < 0) {
            setActiveSlideComponent({
                id: 'welcome-page',
                index: -10
            });
        } else {
            const newFormField = formFields[newActiveSlideIndex];
            setActiveSlideComponent({
                id: newFormField?.id ?? v4(),
                index: newFormField.index
            });
        }

        setFormFields([...formFields]);
    };

    const updateRatingSteps = (slideIndex: number, fieldIndex: number, steps: number, type?: FieldTypes) => {
        formFields![slideIndex]!.properties!.fields![fieldIndex].type = type;
        formFields![slideIndex]!.properties!.fields![fieldIndex].properties = {
            ...(formFields![slideIndex]!.properties!.fields![fieldIndex].properties || {}),
            steps: steps
        };
        setFormFields([...formFields]);
    };

    const resetFields = () => {
        setFormFields([]);
    };

    const getNewField = (field: { name: string; type: FieldTypes; icon: any }, fieldId: string, slideIndex: number) => {
        const fieldIndex = formFields[slideIndex]?.properties?.fields?.length ? formFields[slideIndex]?.properties?.fields?.length! : 0;
        if (field.type === FieldTypes.YES_NO || field.type === FieldTypes.DROP_DOWN || field.type === FieldTypes.MULTIPLE_CHOICE) {
            const firstChoiceId = v4();
            const secondChoiceId = v4();
            return {
                id: fieldId,
                index: fieldIndex,
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
            };
        } else if (field.type === FieldTypes.RATING || field.type === FieldTypes.LINEAR_RATING) {
            return {
                id: fieldId,
                index: fieldIndex,
                type: field.type,
                properties: {
                    fields: [],
                    steps: field.type === FieldTypes.RATING ? 5 : 10
                }
            };
        } else if (field.type === FieldTypes.MATRIX) {
            return {
                id: fieldId,
                index: fieldIndex,
                type: field.type,
                properties: {
                    fields: [
                        {
                            id: v4(),
                            title: '',
                            index: 0,
                            type: FieldTypes.MULTIPLE_CHOICE,
                            properties: {
                                choices: [
                                    {
                                        id: v4(),
                                        value: ''
                                    },
                                    {
                                        id: v4(),
                                        value: ''
                                    }
                                ]
                            }
                        },
                        {
                            id: v4(),
                            title: '',
                            index: 1,
                            type: FieldTypes.MULTIPLE_CHOICE,
                            properties: {
                                choices: [
                                    {
                                        id: v4(),
                                        value: ''
                                    },
                                    {
                                        id: v4(),
                                        value: ''
                                    }
                                ]
                            }
                        }
                    ]
                }
            };
        } else {
            return {
                id: fieldId,
                index: fieldIndex,
                type: field.type
            };
        }
    };

    const updateRowTitle = (rowIndex: number, title: string) => {
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields![rowIndex]!.title = title;
        setFormFields([...formFields]);
    };

    const updateColumnTitle = (columnIndex: number, title: string) => {
        const updatedRows = formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields?.map((field) => {
            field.properties!.choices![columnIndex]!.value = title;
            return field;
        });
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields = [...(updatedRows || [])];
        setFormFields([...formFields]);
    };

    const addColumn = () => {
        const updatedRows = formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields?.map((field) => {
            field.properties!.choices?.push({
                id: v4(),
                value: ''
            });
            return field;
        });
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields = [...(updatedRows || [])];
        setFormFields([...formFields]);
    };

    const addRow = () => {
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields?.push({
            id: v4(),
            title: '',
            type: FieldTypes.MULTIPLE_CHOICE,
            index: formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields!.length + 1,
            properties: { ...formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields![0]!.properties }
        });
        setFormFields([...formFields]);
    };

    const deleteColumn = (columnIndex: number) => {
        const updatedRows = formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields!.map((field) => {
            const updatedChoices = field!.properties!.choices!.filter((choice, index) => index !== columnIndex);
            field!.properties!.choices = updatedChoices;
            return field;
        });

        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields = updatedRows;
        setFormFields([...formFields]);
    };

    const updateAllowMultipleSelectionMatrixField = (allowMultipleSelectionMatrixField: boolean) => {
        const updatedRows = formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields!.map((field: StandardFormFieldDto) => {
            return {
                ...field,
                properties: {
                    ...(field?.properties || {}),
                    allowMultipleSelection: allowMultipleSelectionMatrixField
                }
            };
        });
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields = updatedRows;
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties = {
            ...(formFields?.[activeSlideComponent!.index]?.properties?.fields?.[activeFieldComponent!.index]?.properties || {}),
            allowMultipleSelection: allowMultipleSelectionMatrixField
        };
        setFormFields([...formFields]);
    };

    const deleteRow = (rowIndex: number) => {
        const updatedRows = formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index]!.properties!.fields!.filter((field, index) => index !== rowIndex);
        formFields![activeSlideComponent!.index]!.properties!.fields![activeFieldComponent!.index].properties!.fields = updatedRows;
        setFormFields([...formFields]);
    };

    return {
        formFields,
        setFormFields,
        addField,
        addSlide,
        deleteSlide,
        updateTitle,
        updateDescription,
        updateFieldPlaceholder,
        updateChoiceFieldValue,
        addChoiceField,
        updateFieldRequired,
        updateFieldValidation,
        updateFieldProperty,
        updateShowQuestionNumbers,
        updateAllowMultipleSelectionMatrixField,
        updateSlideTheme,
        updateSlideLayout,
        updateSlideImage,
        updateRatingSteps,
        moveFieldInASlide,
        activeSlide,
        activeField,
        deleteField,
        deleteActiveSlide,
        resetFields,
        addMedia,
        getNewField,
        addSlideFormTemplate,
        removeChoiceField,
        updateFieldImage,
        updateRowTitle,
        updateColumnTitle,
        addRow,
        addColumn,
        deleteRow,
        deleteColumn
    };
}
