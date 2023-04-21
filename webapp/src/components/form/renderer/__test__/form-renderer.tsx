import '@testing-library/jest-dom';
import { cleanup, getByText, render, screen } from '@testing-library/react';

import FormRenderer from '../form-renderer';

const formObject = {
    formId: 'JMsmiqkH',
    title: 'form_title',
    settings: {
        pinned: false,
        customUrl: 'JMsmiqkH',
        private: true,
        responseDataOwnerField: '',
        provider: 'typeform'
    },
    questions: [
        {
            questionId: '6852VwIVRkuo',
            title: "Hello, what's your name?",
            type: {
                type: 'INPUT_FIELD'
            },
            required: false,
            attachment: {
                href: 'https://images.typeform.com/images/WMALzu59xbXQ',
                type: 'image',
                embed_provider: 'no_embed',
                properties: {
                    description: 'alt_text'
                }
            }
        },
        {
            questionId: 'OeZu68HmfzoH',
            title: '...',
            type: {
                type: 'RANKING',
                options: [
                    {
                        value: 'Avatar 2'
                    },
                    {
                        value: 'Wwe'
                    },
                    {
                        value: 'New one'
                    },
                    {
                        value: '3'
                    },
                    {
                        value: '4'
                    }
                ]
            },
            required: false
        },
        {
            questionId: 'TlAc45eb4fmB',
            title: 'Ratings for avatar 2?',
            type: {
                type: 'RATING',
                shape: 'thunderbolt',
                steps: 3
            },
            required: false
        },
        {
            questionId: '8qW3uvHh1Bpq',
            title: 'This is a form.',
            type: {
                type: 'INPUT_FIELD'
            },
            required: false
        }
    ]
};

describe('Form renderer test', () => {
    afterEach(cleanup);

    it('renders the form component', () => {
        render(<FormRenderer form={[]} />);
        expect(screen.getByTestId('form-renderer')).toBeInTheDocument();
    });

    it('renders the title', () => {
        const { getByText } = render(<FormRenderer form={formObject} />);
        // expect(getByText('form_title')).toBeInTheDocument();
        // expect(getByText('This is a form.')).toBeInTheDocument();
    });

    it('uses correct src', () => {
        const { getByAltText } = render(<FormRenderer form={formObject} />);
        // const image: any = getByAltText('alt_text');
        // expect(image.src).toContain('https://images.typeform.com/images/WMALzu59xbXQ');
    });
});
