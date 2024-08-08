import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import ModalButton from '@Components/Common/Input/Button/ModalButton';
import { CheckCircle } from '@mui/icons-material';
import { Autocomplete, Box, createFilterOptions, TextField } from '@mui/material';
import cn from 'classnames';

import { Close } from '@app/Components/icons/close';
import { useModal } from '@app/Components/modal-views/context';
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
        if (responderGroups)
            addFormOnGroup({
                groups: form?.groups || [],
                groupsForUpdate: [...(form?.groups || []), selectedGroup],
                form,
                workspaceId: workspace.id
            });
    };
    return (
        <div className="relative rounded-[8px] bg-white p-10 md:w-[658px]">
            <Close onClick={closeModal} className="absolute right-2 top-2 h-8 w-8 cursor-pointer p-2" />
            <h4 className="h4">{t(formConstant.addgroup.title, { form: form.title })}</h4>
            <p className="body4 !text-black-700 mb-8  mt-2">{t(formConstant.addgroup.description)}</p>
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
                            <Tooltip
                                title={
                                    isFormAlreadyInGroup(form.groups, option.id)
                                        ? t(toolTipConstant.formIsAlreadyOnGroup, {
                                              form: form.title,
                                              group: option.name
                                          })
                                        : ''
                                }
                                key={option.id}
                            >
                                <div>
                                    <Box component="li" {...props} className={cn(' MuiAutocomplete-option !py-2', isFormAlreadyInGroup(form.groups, option.id) && 'pointer-events-none cursor-not-allowed opacity-30')}>
                                        <div className="flex w-full items-center justify-between">
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
                <ModalButton disabled={!selectedGroup} size={ButtonSize.Medium} onClick={handleAddForm}>
                    {t(buttonConstant.add)}
                </ModalButton>
            </div>
        </div>
    );
}
