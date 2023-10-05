import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import ModalButton from '@Components/Common/Input/Button/ModalButton';
import { CheckCircle } from '@mui/icons-material';
import { Autocomplete, Box, TextField, createFilterOptions } from '@mui/material';
import cn from 'classnames';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { isFormAlreadyInGroup } from '@app/utils/groupUtils';


interface IAddFormOnGroupProps {
    forms: Array<StandardFormDto>;
    group: ResponderGroupDto;
}
export default function AddFormOnGroup({ forms, group }: IAddFormOnGroupProps) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const [selectedForm, setSelectedForm] = useState<StandardFormDto | null>(null);
    const { addFormOnGroup } = useGroupForm();
    const workspace = useAppSelector(selectWorkspace);
    const handleAddForm = () => {
        if (selectedForm) {
            addFormOnGroup({ group, groups: selectedForm?.groups, form: selectedForm, workspaceId: workspace.id });
        }
    };
    return (
        <div className="p-10 relative bg-brand-100 md:w-[658px] rounded-[8px]">
            <Close onClick={closeModal} className="absolute top-2 right-2 cursor-pointer p-2 h-8 w-8" />
            <h4 className="h4">{t(buttonConstant.addForm)}</h4>
            <p className="mt-2 mb-8 body4  !text-black-700">{t(groupConstant.form.description)}</p>
            {forms && (
                <Autocomplete
                    disablePortal
                    id="form_list"
                    className="mb-6 mt-5 bg-white"
                    fullWidth
                    onChange={(e, value) => setSelectedForm(value)}
                    value={selectedForm}
                    filterOptions={createFilterOptions({
                        matchFrom: 'start',
                        stringify: (option: StandardFormDto) => option.title
                    })}
                    isOptionEqualToValue={(option: StandardFormDto, value: StandardFormDto) => option.title === value.title}
                    getOptionLabel={(option: StandardFormDto) => option.title}
                    options={forms}
                    sx={{ width: '100%' }}
                    renderOption={(props, option: StandardFormDto) => {
                        return (
                            <Tooltip title={isFormAlreadyInGroup(option.groups, group.id) ? t(toolTipConstant.formIsAlreadyOnGroup, { form: option.title, group: group.name }) : ''} key={option.formId}>
                                <div>
                                    <Box component="li" {...props} className={cn(' MuiAutocomplete-option !py-2', isFormAlreadyInGroup(option.groups, group.id) && 'cursor-not-allowed pointer-events-none opacity-30')}>
                                        <div className="flex justify-between w-full items-center">
                                            {option.title}
                                            {isFormAlreadyInGroup(option.groups, group.id) && <CheckCircle className="h-6 w-6" />}
                                        </div>
                                    </Box>
                                </div>
                            </Tooltip>
                        );
                    }}
                    renderInput={(params) => <TextField {...params} label={t(localesCommon.chooseYourForm)} />}
                />
            )}

            <div className="flex justify-end">
                <ModalButton disabled={!selectedForm} size={ButtonSize.Medium} onClick={handleAddForm}>
                    {t(buttonConstant.add)}
                </ModalButton>
            </div>
        </div>
    );
}