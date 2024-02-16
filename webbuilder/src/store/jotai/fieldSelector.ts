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

    const updateTitle = (fieldId: string, titleText: string) => {
        const newFields = formFields.map((field: FormField) => {
                if (field.id === fieldId) {
                    return {...field, title: titleText}
                } else return field
            }
        )
        setFormFields(newFields)
    }
    const updateFieldPlaceholder = (fieldIndex: number, placeholderText: string) => {
        const newField = formFields[fieldIndex]
        const newFields = formFields.map((field: FormField) => {
                if (field.id === `${fieldIndex}`) {
                    return {...field, properties: {...field.properties, placeholder: placeholderText, fields: []}}
                } else return field
            }
        )
        setFormFields([...formFields,])
    }

    return {formFields, addField, addSlide, updateTitle, updateFieldPlaceholder}
}
