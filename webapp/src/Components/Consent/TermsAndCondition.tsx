import React from 'react';

import CheckBox from '@Components/Common/Input/CheckBox';
import cn from 'classnames';

import { OnlyClassNameInterface } from '@app/models/interfaces';


type TermsAndConditionType = 'normal' | 'title_and_description';

interface TermsAndConditionProps extends OnlyClassNameInterface {
    selected?: boolean;
    onAgree?: (checked: boolean) => void;
    children?: any;
    type?: TermsAndConditionType;
    defaultSelected?: boolean;
}

interface TitleProps extends React.PropsWithChildren {}

interface DescriptionProps extends React.PropsWithChildren {}

const Title: React.FC<React.PropsWithChildren> = ({ children }) => <div className={cn('h6-new')}>{children}</div>;
const Description: React.FC<React.PropsWithChildren> = ({ children }) => <p className="p2">{children}</p>;

const TermsAndCondition: React.FC<TermsAndConditionProps> & {
    Title: React.FC<TitleProps>;
    Description: React.FC<DescriptionProps>;
} = ({ selected, className, onAgree, children, type = 'title_and_description' }) => {
    const handleCheckedChange = () => {
        onAgree && onAgree(!selected);
    };

    if (type === 'normal') {
        return (
            <div className={cn('flex space-x-2', className)}>
                <CheckBox className="!m-0" checked={selected} onClick={handleCheckedChange} />
                <p className="p2">{children}</p>
            </div>
        );
    }
    return (
        <div className={cn('space-y-2', className)}>
            <div className="flex space-x-2 items-center">
                <CheckBox className="!m-0" checked={selected} onClick={handleCheckedChange} />
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