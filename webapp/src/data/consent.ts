import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { ConsentAnswerDto } from '@app/store/consent/types';

const consentPageInformation = {
    title: 'What Is This Page?',
    description: "This page is your opportunity to communicate directly with your form responders about the purpose of the form and the data you collect. It's like a digital handshake, establishing trust and transparency.",
    importanceTitle: 'Why Should You Care?',
    importanceDescription: [
        { title: 'Clear Communication:', description: "This page enables you to communicate your intentions clearly. When responders understand how their data will be used, they're more likely to engage willingly." },
        { title: 'Privacy Matters:', description: "Demonstrating your commitment to data privacy builds a strong foundation of trust. It shows that you value your responders' information and treat it with respect." }
    ]
};

const formPurpose = {
    hint: `Help users understand your form's intent! Specify its purpose
    (e.g., marketing, analytics) for transparent consent.`,
    title: 'Select or Add purpose',
    options: [
        { title: 'Data Collection', type: ConsentType.Checkbox, category: ConsentCategoryType.PurposeOfTheForm },
        { title: 'Marketing', type: ConsentType.Checkbox, category: ConsentCategoryType.PurposeOfTheForm },
        { title: 'Analytics', type: ConsentType.Checkbox, category: ConsentCategoryType.PurposeOfTheForm },
        { title: 'Feedback', type: ConsentType.Checkbox, category: ConsentCategoryType.PurposeOfTheForm },
        { title: 'Data Entry', type: ConsentType.Checkbox, category: ConsentCategoryType.PurposeOfTheForm }
    ],
    category: ConsentCategoryType.PurposeOfTheForm
};

const thirdPartySharing = {
    hint: `Let users know if you're using any third-party apps for form data 
    (e.g., Google Sheets, Google Forms) for transparent consent.`,
    title: 'Select or Add third-Party integrations',
    options: ['No Third-Party', 'Google Sheets', 'Mailchimp', 'Google Analytics']
};

const dataRetention = {
    hint: `Inform users about data retention. Customize how long user data will be stored and whether users can request deletion.`,
    title: 'Data retention options',
    options: [
        { title: 'For a certain number of days', type: ConsentType.Info, category: ConsentCategoryType.DataRetention },
        { title: 'Until a certain date', type: ConsentType.Info, category: ConsentCategoryType.DataRetention },
        { title: 'Forever', type: ConsentType.Info, category: ConsentCategoryType.DataRetention }
    ],
    category: ConsentCategoryType.DataRetention
};

export { consentPageInformation, formPurpose, thirdPartySharing, dataRetention };
