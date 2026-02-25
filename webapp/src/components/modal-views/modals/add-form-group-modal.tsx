import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@app/shadcn/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@app/shadcn/components/ui/popover";
import cn from 'classnames';
import { Check, CheckCircle, ChevronsUpDown } from "lucide-react";

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { isFormAlreadyInGroup } from '@app/utils/group-utils';

interface IAddFormOnGroupProps {
    forms: Array<StandardFormDto>;
    group: ResponderGroupDto;
}

export default function AddFormOnGroup({ forms, group }: IAddFormOnGroupProps) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const [selectedForm, setSelectedForm] = useState<StandardFormDto | null>();
    const [open, setOpen] = useState(false);
    const { addFormOnGroup } = useGroupForm();
    const workspace = useAppSelector(selectWorkspace);
    const handleAddForm = () => {
        if (selectedForm) {
            addFormOnGroup({
                groupsForUpdate: [group],
                groups: selectedForm?.groups || [],
                form: selectedForm,
                workspaceId: workspace.id
            });
        }
    };
    return (
        <div className="relative rounded-[8px] bg-white p-10 md:w-[658px]">
            <Close onClick={closeModal} className="absolute right-2 top-2 h-8 w-8 cursor-pointer p-2" />
            <h4 className="h4">{t(buttonConstant.addForm)}</h4>
            <p className="body4 !text-black-700 mb-8  mt-2">{t(groupConstant.form.description)}</p>
            {forms && (
                <div className="mb-6 mt-5">
                    <Popover open={open} onOpenChange={setOpen}>
                        <PopoverTrigger asChild>
                            <Button
                                variant="ghost"
                                role="combobox"
                                aria-expanded={open}
                                className={cn("w-full justify-between font-normal", !selectedForm && "text-muted-foreground")}
                            >
                                {selectedForm ? selectedForm.title : t(localesCommon.chooseYourForm)}
                                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                            </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[570px] p-0" align="start">
                            <Command>
                                <CommandInput placeholder={"Search forms..."} />
                                <CommandList>
                                    <CommandEmpty>No form found.</CommandEmpty>
                                    <CommandGroup>
                                        {forms.map((form) => (
                                            <CommandItem
                                                key={form.formId}
                                                value={form.title}
                                                onSelect={() => {
                                                    if (isFormAlreadyInGroup(form.groups, group.id)) return;
                                                    setSelectedForm(form)
                                                    setOpen(false)
                                                }}
                                                className={cn(isFormAlreadyInGroup(form.groups, group.id) && "opacity-50 cursor-not-allowed pointer-events-none")}
                                                disabled={isFormAlreadyInGroup(form.groups, group.id)}
                                            >
                                                <Check
                                                    className={cn(
                                                        "mr-2 h-4 w-4",
                                                        selectedForm?.formId === form.formId ? "opacity-100" : "opacity-0"
                                                    )}
                                                />
                                                {form.title}
                                                {isFormAlreadyInGroup(form.groups, group.id) && <CheckCircle className="ml-auto h-4 w-4" />}
                                            </CommandItem>
                                        ))}
                                    </CommandGroup>
                                </CommandList>
                            </Command>
                        </PopoverContent>
                    </Popover>
                </div>
            )}

            <div className="flex justify-end">
                <Button disabled={!selectedForm} onClick={handleAddForm}>
                    {t(buttonConstant.add)}
                </Button>
            </div>
        </div>
    );
}
