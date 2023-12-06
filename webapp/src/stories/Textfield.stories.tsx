import Icon from '@Components/Common/Icons/Common/Plus';
import AppTextField from '@Components/Common/Input/AppTextField';
import type { Meta, StoryObj } from '@storybook/react';
import { StoryFn } from '@storybook/react';

// More on how to set up stories at: https://storybook.js.org/docs/writing-stories#default-export
const meta: Meta<typeof AppTextField> = {
    title: 'Common/TextField',
    component: AppTextField,
    parameters: {
        // Optional parameter to center the component in the Canvas. More info: https://storybook.js.org/docs/configure/story-layout
        layout: 'centered'
    },
    // This component will have an automatically generated Autodocs entry: https://storybook.js.org/docs/writing-docs/autodocs
    tags: ['autodocs'],
    // More on argTypes: https://storybook.js.org/docs/api/argtypes
    argTypes: {}
};

export default meta;

// More on writing stories with args: https://storybook.js.org/docs/writing-stories/args

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
