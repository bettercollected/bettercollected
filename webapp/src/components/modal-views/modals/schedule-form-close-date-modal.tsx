import BottomSheetModalWrapper from "@app/components/modal-views/full-screen-modals/BottomSheetModalWrapper";
import React from "react";
import {DateTimePicker} from "@mui/x-date-pickers";
import {AdapterDayjs} from "@mui/x-date-pickers/AdapterDayjs";
import {LocalizationProvider} from "@mui/x-date-pickers/LocalizationProvider";
import dayjs, {Dayjs} from "dayjs";
import TextField from "@mui/material/TextField";
import AppButton from "@Components/Common/Input/Button/AppButton";
import {ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";
import moment from "moment/moment";
import {useFullScreenModal} from "@app/components/modal-views/full-screen-modal-context";

interface IScheduleFormCloseDateModalProps {
    onFormClosedChange: (date: string | moment.Moment) => void
    closeDate: string
}

export default function ScheduleFormCloseDateModal({onFormClosedChange, closeDate}: IScheduleFormCloseDateModalProps) {

    const [value, setValue] = React.useState<Dayjs | null>(
        closeDate ? dayjs(closeDate) : null
    );

    const {closeModal} = useFullScreenModal()

    const handleChange = (newValue: Dayjs | null) => {
        setValue(newValue);
    };


    return (
        <BottomSheetModalWrapper>
            <div className="flex flex-col items-start gap-[72px] w-full max-w-[660px]">
                <div>
                    <div className="h2-new">Close Form</div>
                    <div className=" w-full flex flex-row justify-between items-center gap-4">
                        <div
                            className="text-sm !text-black-700">
                            This action will ensure that no one can access or fill out the form. You can
                            either schedule a closing date or choose to close it immediately.
                        </div>
                    </div>
                </div>

                <div className="flex flex-col gap-2">
                    <div className="h4-new">
                        Select form closing date
                    </div>
                    <LocalizationProvider dateAdapter={AdapterDayjs}>
                        <DateTimePicker
                            label="Enter a date"
                            value={value}
                            minDateTime={dayjs()}
                            onChange={handleChange}
                            renderInput={(params) => <TextField {...params} />}
                        />
                    </LocalizationProvider>
                </div>
                <div>
                    <AppButton variant={ButtonVariant.Secondary} onClick={() => {
                        onFormClosedChange(moment(value?.toISOString()))
                        closeModal()
                    }}>Schedule Now</AppButton>
                </div>
            </div>
        </BottomSheetModalWrapper>
    )
}