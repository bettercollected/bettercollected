import { ChangeEvent } from 'react';

import AppTextField from '@Components/Common/Input/AppTextField';

import { Close } from '@app/components/icons/close';
import useClickOutsideMenu from '@app/lib/hooks/use-click-outside-menu';
import { resetBuilderMenuState, setUpdateField } from '@app/store/form-builder/actions';
import { selectMenuState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';


export default function MentionedFieldSettings({ field }: { field: IFormFieldState }) {
    const pipingSettingsState = useAppSelector(selectMenuState('pipingFieldSettings'));
    const dispatch = useAppDispatch();

    useClickOutsideMenu('mention-field-settings');
    const onChangeDefaultValue = (event: ChangeEvent<HTMLInputElement>) => {
        dispatch(
            setUpdateField({
                ...field,
                properties: {
                    ...field.properties,
                    mentions: {
                        ...(field?.properties?.mentions || {}),
                        [pipingSettingsState.mentionedFieldId]: event.target.value
                    }
                }
            })
        );
    };

    return (
        <div
            id="mention-field-settings"
            style={{
                position: 'fixed',
                left: pipingSettingsState?.pos?.left,
                top: pipingSettingsState?.pos?.top + 24
            }}
            className={`max-h-48 rounded absolute w-[300px] bg-white drop-shadow-lg top-full z-[100]`}
        >
            <div className="flex p-2 items-center justify-between border-b border-black-200">
                <span className="font-bold">Settings</span>
                <Close
                    className="bg-black-200 p-1"
                    width={16}
                    height={16}
                    onClick={() => {
                        dispatch(resetBuilderMenuState());
                    }}
                />
            </div>
            <div>
                <div className="p-2">
                    <span className="text-sm text-black-800">Default Value</span>
                    <AppTextField placeholder=" " value={field?.properties?.mentions ? field?.properties?.mentions[pipingSettingsState.mentionedFieldId] : ''} onChange={onChangeDefaultValue} />
                </div>
            </div>
        </div>
    );
}