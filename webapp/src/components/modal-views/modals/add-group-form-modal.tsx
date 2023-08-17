import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { CheckCircle } from '@mui/icons-material';
import { Autocomplete, Box, TextField, createFilterOptions } from '@mui/material';
import cn from 'classnames';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/button';
import { formConstant } from '@app/constants/locales/form';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { isFormAlreadyInGroup } from '@app/utils/groupUtils';

interface IAddGroupOnFormProps {
    responderGroups?: Array<ResponderGroupDto>;
    form: StandardFormDto;
}
export default function AddGroupOnForm({ responderGroups, form }: IAddGroupOnFormProps) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const [selectedGroup, setSelectedGroup] = useState<ResponderGroupDto | null>(null);
    const { addFormOnGroup } = useGroupForm();
    const workspace = useAppSelector(selectWorkspace);
    const handleAddForm = () => {
        if (responderGroups) addFormOnGroup({ groups: form.groups, group: selectedGroup, form, workspaceId: workspace.id });
    };
    return (
        <div className="p-10 relative bg-brand-100 md:w-[658px] rounded-[8px]">
            <Close onClick={closeModal} className="absolute top-2 right-2 cursor-pointer p-2 h-8 w-8" />
            <h4 className="h4">{t(formConstant.addgroup.title, { form: form.title })}</h4>
            <p className="mt-2 mb-8 body4  !text-black-700">{t(formConstant.addgroup.description)}</p>
            {responderGroups && (
                <Autocomplete
                    disablePortal
                    id="form_list"
                    className="mb-6 mt-5 bg-white"
                    fullWidth
                    onChange={(e, value) => setSelectedGroup(value)}
                    value={selectedGroup}
                    filterOptions={createFilterOptions({
                        matchFrom: 'start',
                        stringify: (option: ResponderGroupDto) => option.name
                    })}
                    isOptionEqualToValue={(option: ResponderGroupDto, value: ResponderGroupDto) => option.name === value.name}
                    getOptionLabel={(option: ResponderGroupDto) => option.name}
                    options={responderGroups}
                    sx={{ width: '100%' }}
                    renderOption={(props, option: ResponderGroupDto) => {
                        return (
                            <Tooltip title={isFormAlreadyInGroup(form.groups, option.id) ? t(toolTipConstant.formIsAlreadyOnGroup, { form: form.title, group: option.name }) : ''} key={option.id}>
                                <div>
                                    <Box component="li" {...props} className={cn(' MuiAutocomplete-option !py-2', isFormAlreadyInGroup(form.groups, option.id) && 'cursor-not-allowed pointer-events-none opacity-30')}>
                                        <div className="flex justify-between w-full items-center">
                                            {option.name}
                                            {isFormAlreadyInGroup(form.groups, option.id) && <CheckCircle className="h-6 w-6" />}
                                        </div>
                                    </Box>
                                </div>
                            </Tooltip>
                        );
                    }}
                    renderInput={(params) => <TextField {...params} label={t(formConstant.addgroup.label)} />}
                />
            )}

            <div className="flex justify-end">
                <Button disabled={!selectedGroup} size="medium" onClick={handleAddForm}>
                    {t(buttonConstant.add)}
                </Button>
            </div>
        </div>
    );
}
