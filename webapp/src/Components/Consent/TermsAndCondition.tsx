import React, { useState } from 'react';

import CheckBox from '@Components/Common/Input/CheckBox';
import cn from 'classnames';

import { OnlyClassNameInterface } from '@app/models/interfaces';

interface TermsAndConditionProps extends OnlyClassNameInterface {
    selected?: boolean;
    onAgree?: (checked: boolean) => void;
    children?: any;
}

interface TitleProps extends React.PropsWithChildren {}

interface DescriptionProps extends React.PropsWithChildren {}

const Title: React.FC<React.PropsWithChildren> = ({ children }) => <div className={cn('h6-new')}>{children}</div>;
const Description: React.FC<React.PropsWithChildren> = ({ children }) => <p className="p2">{children}</p>;

const TermsAndCondition: React.FC<TermsAndConditionProps> & {
    Title: React.FC<TitleProps>;
    Description: React.FC<DescriptionProps>;
} = ({ selected = true, className, onAgree, children }) => {
    const handleCheckedChange = (_: any, checked: boolean) => {
        onAgree && onAgree(checked);
    };
    return (
        <div className={cn('space-y-2 p-5 border-b border-new-black-300', className)}>
            <div className="flex space-x-2 items-center">
                <CheckBox className="!m-0" defaultChecked={selected} onChange={handleCheckedChange} />
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
