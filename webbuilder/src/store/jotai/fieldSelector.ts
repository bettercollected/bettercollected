'use client';

import {atom, useAtom} from "jotai"
import {FormField} from "@app/models/dtos/form";

const initialFieldsAtom = atom<FormField[]>([])

export default function useFieldSelectorAtom() {
    const [formFields, setFormFields] = useAtom(initialFieldsAtom);

    const addSlide = (field: FormField) => {
        setFormFields([...formFields, field])
    }

    const addField = (slideField: FormField, slideIndex: number) => {
        const slide = formFields[slideIndex]
        slide.properties?.fields.push(slideField)
        const newSlides = formFields.splice(slideIndex, 1, slide)
        setFormFields(newSlides)
    }

    const updateTitle = (fieldIndex:number,slideIndex:number, titleText: string) => {
        const slide = formFields[slideIndex]
        slide.properties!.fields[fieldIndex].title = titleText
        const updatedSlides = [...formFields]
        setFormFields(updatedSlides)
    }
    const updateFieldPlaceholder = (fieldIndex: number,slideIndex:number, placeholderText: string) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields[fieldIndex]['properties'] = slide.properties!.fields[fieldIndex].properties || {fields:[]};
        slide.properties!.fields[fieldIndex]!.properties!.placeholder = placeholderText;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    }


    return {formFields, addField, addSlide, updateTitle, updateFieldPlaceholder}
}
