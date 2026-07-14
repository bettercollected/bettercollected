import { useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@app/shadcn/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@app/shadcn/components/ui/popover";
import cn from 'classnames';
import { Check, CheckCircle, ChevronsUpDown } from "lucide-react";

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { formConstant } from '@app/constants/locales/form';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { isFormAlreadyInGroup } from '@app/utils/group-utils';

interface IAddGroupOnFormProps {
    responderGroups?: Array<ResponderGroupDto>;
    form: StandardFormDto;
}

export default function AddGroupOnForm({ responderGroups, form }: IAddGroupOnFormProps) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const [selectedGroup, setSelectedGroup] = useState<ResponderGroupDto | null>(null);
    const [open, setOpen] = useState(false);
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
                <div className="mb-6 mt-5">
                    <Popover open={open} onOpenChange={setOpen}>
                        <PopoverTrigger asChild>
                            <Button
                                variant="secondary"
                                role="combobox"
                                aria-expanded={open}
                                className={cn("w-full justify-between font-normal", !selectedGroup && "text-muted-foreground")}
                            >
                                {selectedGroup ? selectedGroup.name : t(formConstant.addgroup.label)}
                                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                            </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[570px] p-0" align="start">
                            <Command>
                                <CommandInput placeholder={t(formConstant.addgroup.label)} />
                                <CommandList>
                                    <CommandEmpty>No group found.</CommandEmpty>
                                    <CommandGroup>
                                        {responderGroups.map((group) => (
                                            <CommandItem
                                                key={group.id}
                                                value={group.name}
                                                onSelect={() => {
                                                    if (isFormAlreadyInGroup(form.groups, group.id)) return;
                                                    setSelectedGroup(group)
                                                    setOpen(false)
                                                }}
                                                disabled={isFormAlreadyInGroup(form.groups, group.id)}
                                                className={cn(isFormAlreadyInGroup(form.groups, group.id) && "opacity-50 cursor-not-allowed pointer-events-none")}
                                            >
                                                <Check
                                                    className={cn(
                                                        "mr-2 h-4 w-4",
                                                        selectedGroup?.id === group.id ? "opacity-100" : "opacity-0"
                                                    )}
                                                />
                                                {group.name}
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
                <Button disabled={!selectedGroup} onClick={handleAddForm}>
                    {t(buttonConstant.add)}
                </Button>
            </div>
        </div>
    );
}
