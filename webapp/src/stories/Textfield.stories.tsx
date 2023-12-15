import Icon from '@Components/Common/Icons/Common/Plus';
import AppTextField from '@Components/Common/Input/AppTextField';
import type { Meta, StoryObj } from '@storybook/react';
import { StoryFn } from '@storybook/react';

const meta: Meta<typeof AppTextField> = {
    title: 'Common/TextField',
    component: AppTextField,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {}
};

export default meta;

const Template: StoryFn<typeof AppTextField> = (args) => <AppTextField {...args} />;

type Story = StoryObj<typeof AppTextField>;

export const DateTextField = Template.bind({});
export const TextField = Template.bind({});

export const TextFieldWithError = Template.bind({});

TextField.args = {
    placeholder: 'TextField Placeholder'
};

DateTextField.args = {
    type: 'Date'
};

TextFieldWithError.args = {
    placeholder: 'Error TextField Placeholder',
    isError: true
};

export const DisabledTextFieldWithCustomTextColor: Story = {
    args: {
        isDisabled: true,
        placeholder: 'Disabled Textfield Placeholder'
    }
};

export const TextFieldWithIcon: Story = {
    args: {
        icon: <Icon />,
        placeholder: 'Icon TextField'
    }
};

export const FocusedTextField: Story = {
    args: {
        focused: true,
        placeholder: 'Focused TextField'
    }
};
