import type {Meta, StoryObj} from '@storybook/react';
import AuthAccountProfileImage from "@app/components/auth/account-profile-image";

const meta: Meta<typeof AuthAccountProfileImage> = {
    title: 'Common/AuthProfileImage',
    component: AuthAccountProfileImage,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {}
};

export default meta;
type Story = StoryObj<typeof AuthAccountProfileImage>;

export const Default: Story = {
    args: {
        size: 100,
        image: 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSRUpmVhVLGTZSyVw0A5Fea1ImOodYWycKkKA&usqp=CAU'
    }
};

export const ProfileWithoutImage: Story = {
    args: {
        size: 100,
        name: 'Profile'
    }
};


export const RoundedProfile: Story = {
    args: {
        size: 100,
        name: 'Profile',
        variant: 'rounded'
    }
};

export const CircularProfile: Story = {
    args: {
        size: 100,
        name: 'Profile',
        variant: 'circular'
    }
};

export const SquareProfile: Story = {
    args: {
        size: 100,
        name: 'Profile',
        variant: 'square'
    }
};