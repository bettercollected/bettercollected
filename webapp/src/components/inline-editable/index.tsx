import React from 'react';

import ContentEditable from 'react-contenteditable';
import sanitizeHtml, { AllowedAttribute } from 'sanitize-html';

interface IReactContentEditableProps {
    allowedTags?: Array<string>;
    allowedAttributes?: Record<string, AllowedAttribute[]>;
    tag?: string;
    rows?: number;
    className?: string;
    editable?: boolean;
    content?: string;
    callback?: Function;
}

interface IReactContentEditableStates {}

export default class ReactContentEditable extends React.Component<IReactContentEditableProps, IReactContentEditableStates> {
    state = {
        html: this.props?.content ?? '',
        editable: this.props?.editable ?? true
    };

    sanitizeConfigs = {
        allowedTags: this.props?.allowedTags || [], // Add "h1", "a" or any other tag if you want to pass it here
        allowedAttributes: this.props?.allowedAttributes ?? {} // Add attribute as object like: { a: ["href"] }
    };

    sanitize = () => {
        const sanitizedHtml = sanitizeHtml(this.state.html.replaceAll('&nbsp;', ' ').replaceAll('<div>', '\n').replaceAll('</div>', '').replaceAll('<br>', '\n'), this.sanitizeConfigs);
        return sanitizedHtml;
    };

    handleChange = (evt: any) => {
        this.setState({ html: evt.target.value });
    };

    handleOnBlur = () => {
        const sanitizedHtml = this.sanitize();

        // save to API
        if (!!this.props?.callback) this.props.callback(sanitizedHtml);
    };

    render() {
        const className = this.props?.className ?? '';
        const tag = this.props?.tag ?? 'p';
        const attributes = this.props?.rows && tag === 'textarea' ? { rows: this.props.rows, cols: 20 } : {};

        return (
            <ContentEditable
                className={`editable whitespace-pre-wrap border-none border-r-0 hover:cursor-text focus-visible:outline-none focus:!border-b-2 focus:border-gray-400 ${className}`}
                tagName={tag}
                html={this.state.html} // innerHTML of the editable div
                disabled={!this.state.editable} // use true to disable edition
                onChange={this.handleChange} // handle innerHTML change
                onBlur={this.handleOnBlur}
                {...attributes}
            />
        );
    }
}
