import React, { useState } from 'react';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import BottomSheetModalWrapper from '@Components/Modals/ModalWrappers/BottomSheetModalWrapper';
import dayjs, { Dayjs } from 'dayjs';
import moment from 'moment/moment';
import { format } from 'date-fns';
import { Calendar as CalendarIcon } from 'lucide-react';

import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { Calendar } from '@app/shadcn/components/ui/calendar';
import { cn } from '@app/shadcn/util/lib';

interface IScheduleFormCloseDateModalProps {
    onFormClosedChange: (date: string | moment.Moment) => void;
    closeDate: string;
}

const ScheduleFormCloseDateModal: React.FC<IScheduleFormCloseDateModalProps> = ({ onFormClosedChange, closeDate }) => {
    const [value, setValue] = React.useState<Dayjs | null>(closeDate ? dayjs(closeDate) : null);
    const [isDatePickerOpen, setIsDatePickerOpen] = useState(false);

    const { closeBottomSheetModal } = useBottomSheetModal();

    return (
        <BottomSheetModalWrapper>
            <div className="flex w-full max-w-[660px] flex-col items-start gap-[72px]">
                <div>
                    <div className="h2-new">Close Form</div>
                    <div className="flex w-full flex-row items-center justify-between gap-4">
                        <div className="!text-black-700 text-sm">This action will ensure that no one can access or fill out the form. You can either schedule a closing date or choose to close it immediately.</div>
                    </div>
                </div>

                <div className="flex flex-col gap-2">
                    <div className="h4-new">Select form closing date</div>
                    <Popover
                        open={isDatePickerOpen}
                        onOpenChange={(open: boolean) => {
                            setIsDatePickerOpen(open);
                        }}
                    >
                        <PopoverTrigger asChild>
                            <div className="relative flex w-[280px] cursor-pointer items-center rounded-lg border border-gray-400 bg-white p-2 text-left font-normal text-gray-700">
                                <CalendarIcon className="absolute left-2 h-4 w-4 text-gray-500" />
                                <div className="ml-8 text-black">{value ? format(value, 'PPP') : <span className="text-gray-500">Pick a date</span>}</div>
                            </div>
                        </PopoverTrigger>
                        <PopoverContent className="custom-calendar text-black-900 z-[100000000] w-auto bg-white p-0">
                            <Calendar
                                mode="single"
                                selected={value}
                                onSelect={(value) => {
                                    setValue(value);
                                    setIsDatePickerOpen(false);
                                }}
                                initialFocus
                            />
                        </PopoverContent>
                    </Popover>
                </div>
                <div>
                    <AppButton
                        variant={ButtonVariant.Secondary}
                        onClick={() => {
                            onFormClosedChange(moment(value?.toISOString()));
                            closeBottomSheetModal();
                        }}
                    >
                        Schedule Now
                    </AppButton>
                </div>
            </div>
        </BottomSheetModalWrapper>
    );
};

export default ScheduleFormCloseDateModal;
