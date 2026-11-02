'use client';

import React, { useEffect, useRef } from 'react';

import { useMfaT } from '@app/components/mfa/use-mfa-t';
import { Input } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';

/**
 * One field for the second factor: the six digits an authenticator app shows,
 * or (after "Use a recovery code") one of the ten recovery codes. The browser
 * and password managers are told what it is (`one-time-code`), phones show the
 * number pad for the digits, and an error is announced politely next to it.
 */
export default function CodeEntry({
    id,
    value,
    onChange,
    recovery = false,
    error,
    autoFocus,
    disabled,
    describedBy
}: {
    id: string;
    value: string;
    onChange: (value: string) => void;
    recovery?: boolean;
    error?: string;
    autoFocus?: boolean;
    disabled?: boolean;
    // ids of text that explains the field (the step's introduction), read with it
    describedBy?: string;
}) {
    const { t } = useMfaT();
    const hintId = `${id}-hint`;
    const errorId = `${id}-error`;
    const input = useRef<HTMLInputElement>(null);
    // a step that asks for a code starts in its field
    useEffect(() => {
        if (autoFocus) input.current?.focus();
    }, [autoFocus]);
    return (
        <div className="flex flex-col gap-1.5">
            <label htmlFor={id} className="text-sm font-medium text-black-900">
                {t(recovery ? 'STAFF.MFA.CODE.RECOVERY_LABEL' : 'STAFF.MFA.CODE.LABEL')}
            </label>
            <Input
                ref={input}
                id={id}
                name={recovery ? 'recovery-code' : 'totp-code'}
                type="text"
                value={value}
                disabled={disabled}
                // the number pad and the one-time-code autofill for the digits; a recovery code is typed or pasted
                inputMode={recovery ? 'text' : 'numeric'}
                autoComplete={recovery ? 'off' : 'one-time-code'}
                autoCapitalize={recovery ? 'characters' : 'off'}
                autoCorrect="off"
                spellCheck={false}
                maxLength={recovery ? 24 : 9}
                pattern={recovery ? undefined : '[0-9 ]*'}
                placeholder={recovery ? 'ABCD-EFGH-IJKL-MNOP' : '123 456'}
                aria-describedby={[describedBy, hintId, error ? errorId : undefined].filter(Boolean).join(' ')}
                aria-invalid={error ? true : undefined}
                onChange={(event) => onChange(event.target.value)}
                className={cn('font-mono tracking-widest lg:text-base', error ? 'border-[#C43D3D]' : 'border-control')}
            />
            <p id={hintId} className="text-xs leading-relaxed text-black-700">
                {t(recovery ? 'STAFF.MFA.CODE.RECOVERY_HINT' : 'STAFF.MFA.CODE.HINT')}
            </p>
            {/* always in the page, so that a new message is announced */}
            <p id={errorId} role="status" aria-live="polite" className={cn('text-xs leading-relaxed', error ? 'font-medium text-[#B42318]' : 'sr-only')}>
                {error}
            </p>
        </div>
    );
}
