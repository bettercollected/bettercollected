'use client';

import {atom, useAtom} from "jotai"
import {FormField} from "@app/models/dtos/form";

const initialFieldsAtom = atom<FormField[]>([])

export default function useFieldSelectorAtom() {
    const [fields, setFields] = useAtom(initialFieldsAtom);
    const addField = (field: FormField) => {
        setFields([...fields, field])
    }

    const updateTitle = (fieldId: string, titleText: string) => {
        const newFields = fields.map((field: FormField) => {
                if (field.id === fieldId) {
                    return {...field, title: titleText}
                } else return field
            }
        )
        setFields(newFields)
    }
    const updateFieldPlaceholder = (fieldId: string, placeholderText: string) => {
        const newFields = fields.map((field: FormField) => {
                if (field.id === fieldId) {
                    return {...field, properties: {...field.properties, placeholder: placeholderText, fields: []}}
                } else return field
            }
        )
        setFields(newFields)
    }

    return {fields, setFields, addField, updateTitle, updateFieldPlaceholder}
}
