import type {Meta, StoryObj} from '@storybook/react';
import AppButton from "@Components/Common/Input/Button/AppButton";
import AppTextField from "@Components/Common/Input/AppTextField";
import {ButtonSize} from "@Components/Common/Input/Button/AppButtonProps";
import GenericHalfModal from "@Components/Common/Modals/GenericHalfModal";


const meta: Meta<typeof GenericHalfModal> = {
    title: 'Common/GenericHalfModal',
    component: GenericHalfModal,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {},
    decorators: (Story) => <div className={'relative'}><Story/></div>
};

export default meta;
type Story = StoryObj<typeof GenericHalfModal>;

const Content = () => <div className={'flex flex-col gap-4 pt-2'}>
    <p className={'text-sm text-black-700 '}>It is a generic half modal component story that shows how this component
        renders actually in bettercollected project. It basically is of two type i.e for Confirmation and Danger.</p>
</div>

export const DangerModal = {
    args: {
        children: <Content/>,
        headerTitle: 'Half Screen Modal',
        type: 'danger',
        title: 'Delete Account.',
        subTitle: 'Are you sure you want to delete ?',
        positiveText: 'Delete',
        negativeText: 'Cancel'
    }
}
export const ConfirmModal = {
    args: {
        children: <Content/>,
        headerTitle: 'Half Screen Modal',
        type: 'confirmation',
        title: 'Confirm Account.',
        subTitle: 'Are you sure you want to confirm this?',
        positiveText: 'Yes',
        negativeText: 'No'
    }
}


