'use client';

import * as SelectPrimitive from '@radix-ui/react-select';
import { Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { ASSIGNABLE_ROLES, WorkspaceRole, roleLocale } from '@app/models/enums/workspace-role';
import { Select, SelectContent, SelectTrigger, SelectValue } from '@app/shadcn/components/ui/select';

interface RoleSelectProps {
    value?: WorkspaceRole;
    onChange: (role: WorkspaceRole) => void;
    disabled?: boolean;
    ariaLabel: string;
    className?: string;
}

/** Picks a workspace role; each option carries its one-line description. */
export default function RoleSelect({ value, onChange, disabled, ariaLabel, className }: RoleSelectProps) {
    const { t } = useTranslation();
    return (
        <Select value={value} onValueChange={(role) => onChange(role as WorkspaceRole)} disabled={disabled}>
            <SelectTrigger aria-label={ariaLabel} className={className ?? 'h-9 w-[180px] bg-white'}>
                <SelectValue />
            </SelectTrigger>
            <SelectContent className="max-w-[340px] bg-white">
                {ASSIGNABLE_ROLES.map((role) => (
                    <SelectPrimitive.Item
                        key={role}
                        value={role}
                        className="relative flex w-full cursor-pointer select-none flex-col items-start rounded-sm py-2 pl-8 pr-2 text-sm outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 focus:bg-black-100"
                    >
                        <span className="absolute left-2 top-2.5 flex h-3.5 w-3.5 items-center justify-center">
                            <SelectPrimitive.ItemIndicator>
                                <Check className="h-4 w-4" />
                            </SelectPrimitive.ItemIndicator>
                        </span>
                        <SelectPrimitive.ItemText>{t(roleLocale(role).name)}</SelectPrimitive.ItemText>
                        <span className="mt-0.5 text-xs leading-snug text-black-600">{t(roleLocale(role).description)}</span>
                    </SelectPrimitive.Item>
                ))}
            </SelectContent>
        </Select>
    );
}
