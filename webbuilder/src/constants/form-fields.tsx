import { FieldTypes } from '@app/models/dtos/form';
import DropDownIcon from '@app/views/atoms/Icons/DropDownIcon';
import EmailIcon from '@app/views/atoms/Icons/EmailIcon';
import { LinkIcon } from '@app/views/atoms/Icons/Link';
import MultipleChoiceIcon from '@app/views/atoms/Icons/MultipleChoiceIcon';
import { NumberIcon } from '@app/views/atoms/Icons/NumberIcon';
import PhoneNumberIcon from '@app/views/atoms/Icons/PhoneNumberIcon';
import { TextIcon } from '@app/views/atoms/Icons/Text';
import UploadIcon from '@app/views/atoms/Icons/UploadIcon';
import { YesNoIcon } from '@app/views/atoms/Icons/YesNoIcon';

export const formFieldsList = [
    {
        name: 'Short Input',
        type: FieldTypes.SHORT_TEXT,
        icon: <TextIcon className="h-10 w-10" />
    },
    {
        name: 'Email',
        type: FieldTypes.EMAIL,
        icon: <EmailIcon className="h-10 w-10" />
    },
    {
        name: 'Number',
        type: FieldTypes.NUMBER,
        icon: <NumberIcon className="h-10 w-10" />
    },
    {
        name: 'File Upload',
        type: FieldTypes.FILE_UPLOAD,
        icon: <UploadIcon className="h-10 w-10" />
    },
    { name: 'Link', type: FieldTypes.LINK, icon: <LinkIcon className="h-10 w-10" /> },
    { name: 'Yes No', type: FieldTypes.YES_NO, icon: <YesNoIcon /> },
    { name: 'Drop Down', type: FieldTypes.DROP_DOWN, icon: <DropDownIcon /> },
    {
        name: 'Phone Number',
        type: FieldTypes.PHONE_NUMBER,
        icon: <PhoneNumberIcon className="h-10 w-10" />
    },
    {
        name: 'Multiple Choice',
        type: FieldTypes.MULTIPLE_CHOICE,
        icon: <MultipleChoiceIcon />
    }
];
