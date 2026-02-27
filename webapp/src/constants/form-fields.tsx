import { FieldTypes } from '@app/models/dtos/form';
import { CalenderIcon } from '@Components/icons/calender-icon';
import DropDownIcon from '@Components/icons/dropdown-icon';
import EmailIcon from '@Components/icons/email-icon';
import { LinearRatingIcon } from '@Components/icons/linear-rating';
import { LinkIcon } from '@Components/icons/link';
import MatrixIcon from '@Components/icons/matrix-icon';
import MultipleChoiceIcon from '@Components/icons/multiple-choice-icon';
import { NumberIcon } from '@Components/icons/number-icon';
import PhoneNumberIcon from '@Components/icons/phone-number-icon';
import RatingIcon from '@Components/icons/rating-icon';
import { TextIcon } from '@Components/icons/text';
import UploadIcon from '@Components/icons/upload-icon';
import { YesNoIcon } from '@Components/icons/yes-no-icon';
import { Table2 } from 'lucide-react';

export const formFieldsList = [
    {
        name: 'Text',
        type: FieldTypes.SHORT_TEXT,
        icon: <TextIcon className="h-10 w-10" style={{ color: '#00B0D0' }} />,
        background: '#E6F9FB',
        hoverBackgroundColor: '#B4EEF4'
    },
    {
        name: 'Email',
        type: FieldTypes.EMAIL,
        icon: <EmailIcon className="h-10 w-10" style={{ color: '#796AC7' }} />,
        background: '#F5F3FF',
        hoverBackgroundColor: '#D7D0F7'
    },
    {
        name: 'Phone Number',
        type: FieldTypes.PHONE_NUMBER,
        icon: <PhoneNumberIcon className="h-10 w-10" style={{ color: '#5194C1' }} />,
        background: '#E4F3FD',
        hoverBackgroundColor: '#B4EEF4'
    },
    {
        name: 'Multiple Choice',
        type: FieldTypes.MULTIPLE_CHOICE,
        icon: <MultipleChoiceIcon style={{ color: '#C2A149' }} />,
        background: '#FFF9EB',
        hoverBackgroundColor: '#F8EACA'
    },

    {
        name: 'Upload',
        type: FieldTypes.FILE_UPLOAD,
        icon: <UploadIcon className="h-10 w-10" style={{ color: '#00B0D0' }} />,
        background: '#E6F9FB',
        hoverBackgroundColor: '#B4EEF4'
    },
    {
        name: 'Calendar',
        type: FieldTypes.DATE,
        icon: <CalenderIcon className="h-10 w-10" style={{ color: '#589758' }} />,
        background: '#F0FFF0',
        hoverBackgroundColor: '#CAF8CA'
    },
    {
        name: 'Rating',
        type: FieldTypes.RATING,
        icon: <RatingIcon style={{ color: '#BC6182' }} />,
        background: '#FFEFF5',
        hoverBackgroundColor: '#F8D0DE'
    },
    { name: 'Drop Down', type: FieldTypes.DROP_DOWN, icon: <DropDownIcon style={{ color: '#4D4D4D' }} />, background: '#F6F6F6', hoverBackgroundColor: '#D6D6D6' },

    { name: 'Yes/No', type: FieldTypes.YES_NO, icon: <YesNoIcon style={{ color: '#796AC7' }} />, background: '#F5F3FF', hoverBackgroundColor: '#D7D0F7' },
    {
        name: '1-10 Rate',
        type: FieldTypes.LINEAR_RATING,
        icon: <LinearRatingIcon className="h-10 w-10" style={{ color: '#796AC7' }} />,
        background: '#F5F3FF',
        hoverBackgroundColor: '#D7D0F7'
    },
    {
        name: 'Matrix',
        type: FieldTypes.MATRIX,
        icon: <MatrixIcon style={{ color: '#00B0D0' }} />,
        background: '#E6F9FB',
        hoverBackgroundColor: '#B4EEF4'
    },
    {
        name: 'Table Input',
        type: FieldTypes.TABULAR_INPUT,
        icon: <Table2 size={40} strokeWidth={1.5} style={{ color: '#589758' }} />,
        background: '#F0FFF0',
        hoverBackgroundColor: '#CAF8CA'
    },
    {
        name: 'Number',
        type: FieldTypes.NUMBER,
        icon: <NumberIcon className="h-10 w-10" style={{ color: '#C2A149' }} />,
        background: '#FFF9EB',
        hoverBackgroundColor: '#F8EACA'
    },
    { name: 'Link', type: FieldTypes.LINK, icon: <LinkIcon className="h-10 w-10" />, background: '#F6F6F6', hoverBackgroundColor: '#D6D6D6' }
];
