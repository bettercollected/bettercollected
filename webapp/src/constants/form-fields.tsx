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
import { Banknote, CalendarDays, CalendarRange, Clock, MapPin, PenLine, Repeat, Table2, Tags } from 'lucide-react';

// One quiet treatment for every field type. The picker used to give each type
// its own pastel tile + coloured icon — a rainbow, which is exactly what the
// design language retires (§1): everything saturated must carry meaning, and
// "email is purple, rating is pink" carries none.
const INK_2 = '#344054';

export const formFieldsList = [
    {
        name: 'Text',
        type: FieldTypes.SHORT_TEXT,
        icon: <TextIcon className="h-8 w-8" style={{ color: INK_2 }} />
    },
    {
        name: 'Email',
        type: FieldTypes.EMAIL,
        icon: <EmailIcon className="h-8 w-8" style={{ color: INK_2 }} />
    },
    {
        name: 'Phone Number',
        type: FieldTypes.PHONE_NUMBER,
        icon: <PhoneNumberIcon className="h-8 w-8" style={{ color: INK_2 }} />
    },
    {
        name: 'Multiple Choice',
        type: FieldTypes.MULTIPLE_CHOICE,
        icon: <MultipleChoiceIcon style={{ color: INK_2 }} />
    },
    {
        name: 'Upload',
        type: FieldTypes.FILE_UPLOAD,
        icon: <UploadIcon className="h-8 w-8" style={{ color: INK_2 }} />
    },
    {
        name: 'Calendar',
        type: FieldTypes.DATE,
        icon: <CalenderIcon className="h-8 w-8" style={{ color: INK_2 }} />
    },
    { name: 'Day (d-m-y)', type: FieldTypes.DAY, icon: <CalendarDays size={32} strokeWidth={1.5} style={{ color: INK_2 }} /> },
    { name: 'Time', type: FieldTypes.TIME, icon: <Clock size={32} strokeWidth={1.5} style={{ color: INK_2 }} /> },
    { name: 'Amount of money', type: FieldTypes.CURRENCY, icon: <Banknote size={32} strokeWidth={1.5} style={{ color: INK_2 }} /> },
    { name: 'Date range', type: FieldTypes.DATE_RANGE, icon: <CalendarRange size={32} strokeWidth={1.5} style={{ color: INK_2 }} /> },
    { name: 'Tags', type: FieldTypes.TAGS, icon: <Tags size={32} strokeWidth={1.5} style={{ color: INK_2 }} /> },
    { name: 'Address', type: FieldTypes.ADDRESS, icon: <MapPin size={32} strokeWidth={1.5} style={{ color: INK_2 }} /> },
    { name: 'Signature', type: FieldTypes.SIGNATURE, icon: <PenLine size={32} strokeWidth={1.5} style={{ color: INK_2 }} /> },
    {
        name: 'Rating',
        type: FieldTypes.RATING,
        icon: <RatingIcon style={{ color: INK_2 }} />
    },
    { name: 'Drop Down', type: FieldTypes.DROP_DOWN, icon: <DropDownIcon style={{ color: INK_2 }} /> },
    { name: 'Yes/No', type: FieldTypes.YES_NO, icon: <YesNoIcon style={{ color: INK_2 }} /> },
    {
        name: '1-10 Rate',
        type: FieldTypes.LINEAR_RATING,
        icon: <LinearRatingIcon className="h-8 w-8" style={{ color: INK_2 }} />
    },
    {
        name: 'Matrix',
        type: FieldTypes.MATRIX,
        icon: <MatrixIcon style={{ color: INK_2 }} />
    },
    {
        name: 'Table Input',
        type: FieldTypes.TABULAR_INPUT,
        icon: <Table2 size={32} strokeWidth={1.5} style={{ color: INK_2 }} />
    },
    {
        name: 'Number',
        type: FieldTypes.NUMBER,
        icon: <NumberIcon className="h-8 w-8" style={{ color: INK_2 }} />
    },
    { name: 'Link', type: FieldTypes.LINK, icon: <LinkIcon className="h-8 w-8" style={{ color: INK_2 }} /> },
    {
        // Questions answered once per item (applicant, employer, ...).
        name: 'Repeating group',
        type: FieldTypes.GROUP,
        icon: <Repeat size={30} strokeWidth={1.5} style={{ color: INK_2 }} />
    }
];
