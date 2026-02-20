import { AppInput } from '@app/shadcn/components/ui/input';
import Icon from '@Components/Common/Icons/Common/Plus';
import type { Meta, StoryObj } from '@storybook/react';
import { StoryFn } from '@storybook/react';

const meta: Meta<typeof AppInput> = {
    title: 'Common/TextField',
    component: AppInput,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {}
};

export default meta;

const Template: StoryFn<typeof AppInput> = (args) => <AppInput {...args} />;

type Story = StoryObj<typeof AppInput>;

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
};

export const DisabledTextFieldWithCustomTextColor: Story = {
    args: {
        disabled: true,
        placeholder: 'Disabled Textfield Placeholder'
    }
};

export const TextFieldWithIcon: Story = {
    args: {
        icon: <Icon />,
        placeholder: 'Icon TextField'
    }
};


