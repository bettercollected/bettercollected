'use client';

import { JSONContent } from '@tiptap/react';
import { atom, useAtom } from 'jotai';
import { v4 } from 'uuid';

import { FieldTypes, FormField } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import {
    useActiveFieldComponent,
    useActiveSlideComponent
} from '@app/store/jotai/activeBuilderComponent';
import { reorder } from '@app/utils/arrayUtils';

const initialFieldsAtom = atom<FormField[]>([
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
                        placeholder: 'Your full name please'
                    }
                }
            ]
        },
        imageUrl:
            'https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2defaultImage.png'
    }
]);

export default function useFormFieldsAtom() {
    const [formFields, setFormFields] = useAtom(initialFieldsAtom);

    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent, setActiveFieldComponent } = useActiveFieldComponent();

    const addSlide = (field: FormField) => {
        setFormFields([...formFields, field]);
    };

    const deleteSlide = (slideIndex: number) => {
        formFields.splice(slideIndex, 1);
        const updatedFormFields = formFields?.map((slide: FormField, index) => {
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
        if (activeSlideComponent?.index !== undefined)
            return formFields[activeSlideComponent!.index];
        return;
    };

    const activeSlide = getActiveSlide();

    const getActiveField = () => {
        if (activeFieldComponent?.index !== undefined)
            return activeSlide?.properties?.fields![activeFieldComponent.index];
        return;
    };
    const activeField = getActiveField();

    const addField = (slideField: FormField, slideIndex: number) => {
        const slide = formFields[slideIndex];
        slide.properties?.fields!.push(slideField);
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateTitle = (
        fieldIndex: number,
        slideIndex: number,
        titleText: JSONContent
    ) => {
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

    const updateDescription = (
        fieldIndex: number,
        slideIndex: number,
        description: string | undefined
    ) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex].description = description;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateFieldPlaceholder = (
        fieldIndex: number,
        slideIndex: number,
        placeholderText: string
    ) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex]['properties'] = slide.properties!.fields![
            fieldIndex
        ].properties || { fields: [] };
        slide.properties!.fields![fieldIndex]!.properties!.placeholder =
            placeholderText;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateChoiceFieldValue = (
        fieldIndex: number,
        slideIndex: number,
        choiceId: string,
        choiceValue: string
    ) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex]!.properties!.choices =
            slide.properties!.fields![fieldIndex]?.properties?.choices?.map(
                (choice) => {
                    if (choice.id === choiceId) {
                        choice.value = choiceValue;
                        return choice;
                    } else return choice;
                }
            );
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

    const updateFieldRequired = (
        fieldIndex: number,
        slideIndex: number,
        required: boolean
    ) => {
        formFields[slideIndex].properties!.fields![fieldIndex].validations = {
            ...formFields[slideIndex].properties!.fields![fieldIndex].validations,
            required: required
        };
        setFormFields([...formFields]);
    };

    const updateFieldValidation = (
        fieldIndex: number,
        slideIndex: number,
        validation: any
    ) => {
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

    const updateSlideTheme = (color: {
        title: string;
        primary: string;
        secondary: string;
        tertiary: string;
        accent: string;
    }) => {
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
        if (!formFields[activeSlide?.index || 0].imageUrl) {
            formFields[activeSlide?.index || 0].imageUrl =
                'https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2defaultImage.png';
        }
        formFields[activeSlide?.index || 0].properties!.layout = layout;
        setFormFields([...formFields]);
    };

    const updateSlideImage = (imageUrl: string) => {
        formFields[activeSlide?.index || 0].imageUrl = imageUrl;
        setFormFields([...formFields]);
    };

    const moveFieldInASlide = (
        slideIndex: number,
        sourceIndex: number,
        destinationIndex: number
    ) => {
        formFields![slideIndex]!.properties!.fields = reorder(
            formFields![slideIndex]!.properties!.fields!,
            sourceIndex,
            destinationIndex
        );
        setFormFields([...formFields]);
    };

    const updateFieldProperty = (
        fieldIndex: number,
        slideIndex: number,
        property: string,
        value: any
    ) => {
        formFields![slideIndex]!.properties!.fields![fieldIndex].properties = {
            ...(formFields![slideIndex]!.properties!.fields![fieldIndex].properties ||
                {}),
            [property]: value
        };
        setFormFields([...formFields]);
    };

    const deleteField = (slideIndex: number, fieldIndex: number) => {
        formFields![slideIndex]!.properties!.fields!.splice(fieldIndex, 1);
        formFields![slideIndex!].properties!.fields = formFields![
            slideIndex!
        ].properties!.fields?.map((field, index) => ({ ...field, index }));
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

    const updateRatingSteps = (
        slideIndex: number,
        fieldIndex: number,
        steps: number,
        type?: FieldTypes
    ) => {
        formFields![slideIndex]!.properties!.fields![fieldIndex].type = type;
        formFields![slideIndex]!.properties!.fields![fieldIndex].properties = {
            ...(formFields![slideIndex]!.properties!.fields![fieldIndex].properties ||
                {}),
            steps: steps
        };
        setFormFields([...formFields]);
    };

    const resetFields = () => {
        setFormFields([]);
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
        addMedia
    };
}
