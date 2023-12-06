import { ComponentProps } from 'react';

import Icon from '@Components/Common/Icons/Common/Plus';
import AppButton, { AppButtonProps } from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { StoryFn } from '@storybook/react';
import type { Meta, StoryObj } from '@storybook/react';

// More on how to set up stories at: https://storybook.js.org/docs/writing-stories#default-export
const meta: Meta<typeof AppButton> = {
    title: 'Common/Button',
    component: AppButton,
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
type Story = StoryObj<typeof AppButton>;

// More on writing stories with args: https://storybook.js.org/docs/writing-stories/args

const Template: StoryFn<AppButtonProps> = (args) => <AppButton {...args} />;

export const ButtonWithIcon = Template.bind({});

export const ButtonWithPostFixIcon = Template.bind({});

ButtonWithPostFixIcon.args = {
    variant: ButtonVariant.Primary,
    children: 'PostFix Icon Button',
    disabled: false,
    postFixIcon: <Icon />
};

ButtonWithIcon.args = {
    variant: ButtonVariant.Primary,
    children: 'Prefix Icon Button',
    disabled: false,
    icon: <Icon />
};

export const Primary: Story = {
    args: {
        variant: ButtonVariant.Primary,
        children: 'Primary Button',
        disabled: false
    }
};

export const Secondary: Story = {
    args: {
        variant: ButtonVariant.Secondary,
        children: 'Secondary Button',
        disabled: false
    }
};
export const Tertiary: Story = {
    args: {
        variant: ButtonVariant.Tertiary,
        children: 'Tertiary Button',
        disabled: false
    }
};

export const Ghost: Story = {
    args: {
        variant: ButtonVariant.Ghost,
        children: 'Ghost Button',
        disabled: false
    }
};

export const DangerGhost: Story = {
    args: {
        variant: ButtonVariant.DangerGhost,
        children: 'DangerGhost Button',
        disabled: false
    }
};

export const Danger: Story = {
    args: {
        variant: ButtonVariant.Danger,
        children: 'Danger Button',
        disabled: false
    }
};
