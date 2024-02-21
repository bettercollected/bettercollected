import {FieldTypes} from "@app/models/dtos/form";

export const formFieldsList = [
    {name: "Short Input", type: FieldTypes.SHORT_TEXT},
    {name: "Email", type: FieldTypes.EMAIL},
    {name: "Number", type: FieldTypes.NUMBER},
    {name: "File Upload", type: FieldTypes.FILE_UPLOAD},
    {name: "Link", type: FieldTypes.LINK},
    {name: 'Yes No', type: FieldTypes.YES_NO},
    {name: 'Drop Down', type: FieldTypes.DROP_DOWN},
    {name: 'Phone Number', type: FieldTypes.PHONE_NUMBER},
    {name: 'Multiple Choice', type: FieldTypes.MULTIPLE_CHOICE}
]