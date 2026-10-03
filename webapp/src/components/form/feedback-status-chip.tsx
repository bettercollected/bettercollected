import cn from 'classnames';

import { statusTone, statusToneClass } from '@app/utils/respondent-feedback';

/** A submission's feedback status ("Selected"), coloured by what it says. */
export default function FeedbackStatusChip({ status, className }: { status: string; className?: string }) {
    return <span className={cn('w-fit rounded-full px-2 py-0.5 text-xs font-medium', statusToneClass[statusTone(status)], className)}>{status}</span>;
}
