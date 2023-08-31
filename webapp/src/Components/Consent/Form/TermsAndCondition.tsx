import React from 'react';

import CheckBox from '@Components/Common/Input/CheckBox';
import cn from 'classnames';

import { OnlyClassNameInterface } from '@app/models/interfaces';

interface TermsAndConditionProps extends OnlyClassNameInterface {
    selected?: boolean;
    onAgree?: any;
    children?: any;
}

interface TitleProps extends OnlyClassNameInterface {
    title: string;
}

interface DescriptionProps {
    description: string;
}

const Title: React.FC<TitleProps> = ({ title, className }) => <div className={cn('h6-new', className)}>{title}</div>;

const Description: React.FC<DescriptionProps> = ({ description }) => (
    <div className="space-y-2">
        <p className="p2">{description}</p>
    </div>
);

const TermsAndCondition: React.FC<TermsAndConditionProps> & {
    Title: React.FC<TitleProps>;
    Description: React.FC<DescriptionProps>;
} = ({ selected = true, className, onAgree, children }) => {
    return (
        <div className={cn('space-y-2 p-5 border-b border-new-black-300', className)}>
            <div className="flex space-x-2 items-center">
                <CheckBox className="!m-0" checked={selected} />
                {React.Children.map(children, (child) => {
                    if (React.isValidElement(child) && child.type === Title) {
                        return child;
                    }
                    return null;
                })}
            </div>
            {React.Children.map(children, (child) => {
                if (React.isValidElement(child) && child.type === Description) {
                    return child;
                }
                return null;
            })}
        </div>
    );
};

TermsAndCondition.Title = Title;
TermsAndCondition.Description = Description;

export default TermsAndCondition;
