import { FieldTypes } from '@app/models/dtos/form';
import { CalenderIcon } from '@app/views/atoms/Icons/CalendarIcon';
import DropDownIcon from '@app/views/atoms/Icons/DropDownIcon';
import EmailIcon from '@app/views/atoms/Icons/EmailIcon';
import { LinearRatingIcon } from '@app/views/atoms/Icons/LinearRating';
import { LinkIcon } from '@app/views/atoms/Icons/Link';
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
        icon: <TextIcon className="h-10 w-10" />
    },
    {
        name: 'Email',
        type: FieldTypes.EMAIL,
        icon: <EmailIcon className="h-10 w-10" />
    },
    {
        name: 'Phone Number',
        type: FieldTypes.PHONE_NUMBER,
        icon: <PhoneNumberIcon className="h-10 w-10" />
    },
    {
        name: 'Multiple Choice',
        type: FieldTypes.MULTIPLE_CHOICE,
        icon: <MultipleChoiceIcon />
    },

    {
        name: 'Upload',
        type: FieldTypes.FILE_UPLOAD,
        icon: <UploadIcon className="h-10 w-10" />
    },
    {
        name: 'Calendar',
        type: FieldTypes.DATE,
        icon: <CalenderIcon className="h-10 w-10" />
    },
    {
        name: 'Rating',
        type: FieldTypes.RATING,
        icon: <RatingIcon />
    },
    { name: 'Drop Down', type: FieldTypes.DROP_DOWN, icon: <DropDownIcon /> },

    {
        name: 'Number',
        type: FieldTypes.NUMBER,
        icon: <NumberIcon className="h-10 w-10" />
    },
    { name: 'Link', type: FieldTypes.LINK, icon: <LinkIcon className="h-10 w-10" /> },
    { name: 'Yes/No', type: FieldTypes.YES_NO, icon: <YesNoIcon /> },

    {
        name: '1-10 Rate',
        type: FieldTypes.LINEAR_RATING,
        icon: <LinearRatingIcon className="h-10 w-10" />
    }
];
