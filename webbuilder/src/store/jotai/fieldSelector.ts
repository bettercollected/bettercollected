'use client';

import {atom, useAtom} from "jotai"
import {FieldTagName} from "@app/models/enums/fieldEnum";

export interface IFieldType {
    fieldId: string;
    label: string;
    fieldType: FieldTagName;
    placeholder: string;
}

const initialFieldAtom = atom<IFieldType[]>([])

export default function useFieldSelectorAtom() {
    const [fields, setFields] = useAtom(initialFieldAtom);
    const addField = (field: IFieldType) => {
        setFields([...fields, field])
    }

    const updateLabel = (fieldId: string, labelText: string) => {
        const updatedFields = fields.map((field: IFieldType) => {
            if (field.fieldId === fieldId) {
                return {...field, label: labelText}
            } else return field
        })
        setFields(updatedFields)
    }

    const updatePlaceholder = (fieldId: string, placeholderText: string) => {
        const updatedFields = fields.map((field: IFieldType) => {
            if (field.fieldId === fieldId) {
                return {...field, placeholder: placeholderText}
            } else return field
        })
        setFields(updatedFields)
    }


    return {fields, setFields, addField, updateLabel, updatePlaceholder}
}
