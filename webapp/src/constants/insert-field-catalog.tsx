import { ReactNode } from 'react';

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
import { AlignLeft, Calculator, Image as ImageIcon, Repeat, Table2, Type, Video } from 'lucide-react';

import { FieldTypes } from '@app/models/dtos/form';

/**
 * What the Insert menu offers: every field type a creator can add, grouped
 * the way people think about them, each with a one-line description and the
 * words people search for. One quiet ink for every icon (no per-type colours).
 */

export type InsertCategory = 'Text' | 'Choice' | 'Scale' | 'Date & number' | 'Files' | 'Layout & content';

export const INSERT_CATEGORIES: InsertCategory[] = ['Text', 'Choice', 'Scale', 'Date & number', 'Files', 'Layout & content'];

export interface InsertCatalogItem {
    type: FieldTypes;
    name: string;
    description: string;
    category: InsertCategory;
    /** Extra words that find this item in the search box. */
    keywords: string[];
    icon: ReactNode;
}

const INK_2 = '#344054';
const ICON = 'h-5 w-5';
const iconStyle = { color: INK_2 };

export const insertCatalog: InsertCatalogItem[] = [
    { type: FieldTypes.SHORT_TEXT, name: 'Short text', description: 'A one-line answer, like a name', category: 'Text', keywords: ['text', 'input', 'name', 'single line'], icon: <TextIcon className={ICON} style={iconStyle} /> },
    {
        type: FieldTypes.LONG_TEXT,
        name: 'Long text',
        description: 'A longer answer over several lines',
        category: 'Text',
        keywords: ['paragraph', 'textarea', 'comment', 'multi line'],
        icon: <AlignLeft className={ICON} strokeWidth={1.75} style={iconStyle} />
    },
    { type: FieldTypes.EMAIL, name: 'Email', description: 'An email address, checked as typed', category: 'Text', keywords: ['mail', 'address', 'contact'], icon: <EmailIcon className={ICON} style={iconStyle} /> },
    { type: FieldTypes.PHONE_NUMBER, name: 'Phone number', description: 'A phone number with country code', category: 'Text', keywords: ['telephone', 'mobile', 'contact'], icon: <PhoneNumberIcon className={ICON} style={iconStyle} /> },
    { type: FieldTypes.LINK, name: 'Link', description: 'A web address', category: 'Text', keywords: ['url', 'website'], icon: <LinkIcon className={ICON} style={iconStyle} /> },
    { type: FieldTypes.TABULAR_INPUT, name: 'Table input', description: 'Text answers in rows and columns', category: 'Text', keywords: ['table', 'grid', 'spreadsheet'], icon: <Table2 className={ICON} strokeWidth={1.75} style={iconStyle} /> },
    { type: FieldTypes.MULTIPLE_CHOICE, name: 'Multiple choice', description: 'Pick one or more from a list', category: 'Choice', keywords: ['options', 'radio', 'checkbox', 'select'], icon: <MultipleChoiceIcon className={ICON} style={iconStyle} /> },
    { type: FieldTypes.DROP_DOWN, name: 'Drop down', description: 'Pick one from a compact list', category: 'Choice', keywords: ['dropdown', 'select', 'options', 'menu'], icon: <DropDownIcon className={ICON} style={iconStyle} /> },
    { type: FieldTypes.YES_NO, name: 'Yes/No', description: 'A simple yes or no', category: 'Choice', keywords: ['boolean', 'yes', 'no', 'confirm'], icon: <YesNoIcon className={ICON} style={iconStyle} /> },
    { type: FieldTypes.MATRIX, name: 'Matrix', description: 'The same choices for several rows', category: 'Choice', keywords: ['grid', 'likert', 'rows', 'columns'], icon: <MatrixIcon className={ICON} style={iconStyle} /> },
    { type: FieldTypes.RATING, name: 'Rating', description: 'Stars from 1 to 5', category: 'Scale', keywords: ['stars', 'score'], icon: <RatingIcon className={ICON} style={iconStyle} /> },
    { type: FieldTypes.LINEAR_RATING, name: '1-10 Rate', description: 'A score on a 1 to 10 scale', category: 'Scale', keywords: ['scale', 'nps', 'linear', 'score', 'opinion'], icon: <LinearRatingIcon className={ICON} style={iconStyle} /> },
    { type: FieldTypes.DATE, name: 'Date', description: 'A day picked from a calendar', category: 'Date & number', keywords: ['calendar', 'day', 'birthday'], icon: <CalenderIcon className={ICON} style={iconStyle} /> },
    { type: FieldTypes.NUMBER, name: 'Number', description: 'A number, such as an amount', category: 'Date & number', keywords: ['amount', 'quantity', 'digits'], icon: <NumberIcon className={ICON} style={iconStyle} /> },
    {
        type: FieldTypes.CALCULATED,
        name: 'Calculation',
        description: 'A total or score worked out from answers',
        category: 'Date & number',
        keywords: ['calculated', 'formula', 'total', 'sum', 'score', 'price', 'compute'],
        icon: <Calculator className={ICON} strokeWidth={1.75} style={iconStyle} />
    },
    { type: FieldTypes.FILE_UPLOAD, name: 'File upload', description: 'A document or photo, up to 25 MB', category: 'Files', keywords: ['upload', 'attachment', 'document', 'photo'], icon: <UploadIcon className={ICON} style={iconStyle} /> },
    {
        type: FieldTypes.TEXT,
        name: 'Text block',
        description: 'A heading or explanation, nothing to answer',
        category: 'Layout & content',
        keywords: ['heading', 'statement', 'paragraph', 'title', 'intro'],
        icon: <Type className={ICON} strokeWidth={1.75} style={iconStyle} />
    },
    { type: FieldTypes.IMAGE_CONTENT, name: 'Image', description: 'A picture shown on the page', category: 'Layout & content', keywords: ['picture', 'photo', 'media'], icon: <ImageIcon className={ICON} strokeWidth={1.75} style={iconStyle} /> },
    { type: FieldTypes.VIDEO_CONTENT, name: 'Video', description: 'A YouTube or Vimeo video', category: 'Layout & content', keywords: ['youtube', 'vimeo', 'media', 'embed'], icon: <Video className={ICON} strokeWidth={1.75} style={iconStyle} /> },
    { type: FieldTypes.GROUP, name: 'Repeating group', description: 'Questions answered once per item', category: 'Layout & content', keywords: ['repeat', 'loop', 'list', 'section'], icon: <Repeat className={ICON} strokeWidth={1.75} style={iconStyle} /> }
];

/**
 * Which of the (filtered) items a search should highlight: the first whose
 * name starts with the query ("number" → Number, not Phone number), else
 * the first one.
 */
export function bestInsertMatch(items: InsertCatalogItem[], query: string): number {
    const q = query.trim().toLowerCase();
    if (!q) return 0;
    const index = items.findIndex((item) => item.name.toLowerCase().startsWith(q));
    return index >= 0 ? index : 0;
}

/** The catalog item for a field type, if the menu offers it. */
export function insertCatalogItem(type?: string | null): InsertCatalogItem | undefined {
    return insertCatalog.find((item) => item.type === type);
}

/**
 * The items matching a search, in menu order (grouped by category). Every
 * word of the query must match the start of a word in the item's name,
 * category or keywords, or appear in its description.
 */
export function filterInsertCatalog(query: string, items: InsertCatalogItem[] = insertCatalog): InsertCatalogItem[] {
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    const ordered = INSERT_CATEGORIES.flatMap((category) => items.filter((item) => item.category === category));
    if (!terms.length) return ordered;
    return ordered.filter((item) => {
        const words = [item.name, item.category, ...item.keywords]
            .join(' ')
            .toLowerCase()
            .split(/[\s/&-]+/)
            .filter(Boolean);
        const description = item.description.toLowerCase();
        return terms.every((term) => words.some((word) => word.startsWith(term)) || description.includes(term));
    });
}
