import type { Locale } from 'date-fns';
import { enGB, nl } from 'date-fns/locale';

/** The date-fns locale (month and weekday names, date order) for a staff language. */
export const dateFnsLocale = (language: string | undefined): Locale => (language?.startsWith('nl') ? nl : enGB);
