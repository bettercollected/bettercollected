import { Button } from '@app/shadcn/components/ui/button';
import BottomSheetModalWrapper from '@Components/modals/modal-wrapper/bottom-sheet-modal-wrapper';
import { format } from 'date-fns';
import dayjs from 'dayjs';
import { Calendar as CalendarIcon } from 'lucide-react';
import moment from 'moment/moment';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { dateFnsLocale } from '@app/lib/date-fns-locale';

import { Calendar } from '@app/shadcn/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { useBottomSheetModal } from '@Components/modals/contexts/bottom-sheet-modal-context';

interface IScheduleFormCloseDateModalProps {
    onFormClosedChange: (date: string | moment.Moment) => void;
    closeDate: string;
}

const ScheduleFormCloseDateModal: React.FC<IScheduleFormCloseDateModalProps> = ({ onFormClosedChange, closeDate }) => {
    const { t, i18n } = useTranslation();
    const [value, setValue] = React.useState<Date | null>(closeDate ? new Date(closeDate) : null);
    const [isDatePickerOpen, setIsDatePickerOpen] = useState(false);

    const { closeBottomSheetModal } = useBottomSheetModal();

    // Set the minimum date to tommorow
    const minDate = dayjs().add(1, 'day').startOf('day').toDate();

    return (
        <BottomSheetModalWrapper>
            <div className="flex w-full max-w-[660px] flex-col items-start gap-[72px]">
                <div>
                    <div className="h2-new">{t('STAFF.MODALS.SCHEDULE_TITLE')}</div>
                    <div className="flex w-full flex-row items-center justify-between gap-4">
                        <div className="text-black-700! text-sm">{t('STAFF.MODALS.SCHEDULE_INTRO')}</div>
                    </div>
                </div>

                <div className="flex flex-col gap-2">
                    <div id="close-date-label" className="h4-new">
                        {t('STAFF.MODALS.SCHEDULE_LABEL')}
                    </div>
                    <Popover
                        open={isDatePickerOpen}
                        onOpenChange={(open: boolean) => {
                            setIsDatePickerOpen(open);
                        }}
                    >
                        <PopoverTrigger asChild>
                            {/* A real button, so the date picker opens from the keyboard too. */}
                            <button
                                type="button"
                                aria-labelledby="close-date-label close-date-value"
                                className="border-black-300 text-black-700 hover:border-black-400 focus-visible:ring-brand-500 relative flex w-[280px] max-w-full cursor-pointer items-center rounded border bg-white p-2 text-left font-normal transition-colors focus:outline-hidden focus-visible:ring-2"
                            >
                                <CalendarIcon aria-hidden="true" className="text-black-600 absolute left-2 h-4 w-4" />
                                <span id="close-date-value" className="text-black-900 ml-8">
                                    {value ? format(value, 'PPP', { locale: dateFnsLocale(i18n.language) }) : <span className="text-black-600">{t('STAFF.MODALS.PICK_DATE')}</span>}
                                </span>
                            </button>
                        </PopoverTrigger>

                        <PopoverContent className="custom-calendar text-black-900 w-auto bg-white p-0">
                            <Calendar
                                mode="single"
                                selected={value ? value : undefined} // Convert Dayjs to Date or pass undefined if value is null
                                onSelect={(selectedDate?: Date) => {
                                    setValue(selectedDate || null);
                                    setIsDatePickerOpen(false);
                                }}
                                autoFocus
                                locale={dateFnsLocale(i18n.language)}
                                disabled={{ before: minDate }} // Set the minimum date to tomorrow
                            />
                        </PopoverContent>
                    </Popover>
                </div>
                <div>
                    <Button
                        variant="secondary"
                        onClick={() => {
                            onFormClosedChange(moment(value?.toISOString()));
                            closeBottomSheetModal();
                        }}
                    >
                        {t('STAFF.MODALS.SCHEDULE_NOW')}
                    </Button>
                </div>
            </div>
        </BottomSheetModalWrapper>
    );
};

export default ScheduleFormCloseDateModal;
