import { FieldTypes } from '@app/models/dtos/form';
import { CalenderIcon } from '@app/views/atoms/Icons/CalendarIcon';
import DropDownIcon from '@app/views/atoms/Icons/DropDownIcon';
import EmailIcon from '@app/views/atoms/Icons/EmailIcon';
import { LinearRatingIcon } from '@app/views/atoms/Icons/LinearRating';
import { LinkIcon } from '@app/views/atoms/Icons/Link';
import MatrixIcon from '@app/views/atoms/Icons/MartixIcon';
import MultipleChoiceIcon from '@app/views/atoms/Icons/MultipleChoiceIcon';
import { NumberIcon } from '@app/views/atoms/Icons/NumberIcon';
import PhoneNumberIcon from '@app/views/atoms/Icons/PhoneNumberIcon';
import RatingIcon from '@app/views/atoms/Icons/RatingIcon';
import { TextIcon } from '@app/views/atoms/Icons/Text';
import UploadIcon from '@app/views/atoms/Icons/UploadIcon';
import { YesNoIcon } from '@app/views/atoms/Icons/YesNoIcon';

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
        name: 'Number',
        type: FieldTypes.NUMBER,
        icon: <NumberIcon className="h-10 w-10" style={{ color: '#C2A149' }} />,
        background: '#FFF9EB',
        hoverBackgroundColor: '#F8EACA'
    },
    { name: 'Link', type: FieldTypes.LINK, icon: <LinkIcon className="h-10 w-10" />, background: '#F6F6F6', hoverBackgroundColor: '#D6D6D6' }
];
