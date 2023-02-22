export const importTypeformArrayMock = [
    {
        id: 'UJs4vZ7O',
        type: 'quiz',
        title: 'All Fields',
        last_updated_at: '2023-01-18T10:36:19.088046Z',
        created_at: '2023-01-18T10:06:57.763663Z',
        settings: {
            is_public: true,
            is_trial: false
        },
        self: {
            href: 'https://api.typeform.com/forms/UJs4vZ7O'
        },
        theme: {
            href: 'https://api.typeform.com/themes/qHWOQ7'
        },
        _links: {
            display: 'https://grntn54tvzi.typeform.com/to/UJs4vZ7O'
        }
    },
    {
        id: 'dxVGxhxu',
        type: 'quiz',
        title: 'Text Only',
        last_updated_at: '2023-01-17T09:42:34.600203Z',
        created_at: '2023-01-17T09:39:52.742088Z',
        settings: {
            is_public: true,
            is_trial: false
        },
        self: {
            href: 'https://api.typeform.com/forms/dxVGxhxu'
        },
        theme: {
            href: 'https://api.typeform.com/themes/qHWOQ7'
        },
        _links: {
            display: 'https://grntn54tvzi.typeform.com/to/dxVGxhxu'
        }
    },
    {
        id: 'lONHr3TI',
        type: 'quiz',
        title: 'Grid Answer Field',
        last_updated_at: '2023-01-17T07:44:12.601178Z',
        created_at: '2023-01-17T07:40:41.086675Z',
        settings: {
            is_public: true,
            is_trial: false
        },
        self: {
            href: 'https://api.typeform.com/forms/lONHr3TI'
        },
        theme: {
            href: 'https://api.typeform.com/themes/qHWOQ7'
        },
        _links: {
            display: 'https://grntn54tvzi.typeform.com/to/lONHr3TI'
        }
    },
    {
        id: 'obZZBjd4',
        type: 'quiz',
        title: 'My typeform',
        last_updated_at: '2023-01-25T07:58:01.076087Z',
        created_at: '2022-08-08T04:51:13.850471Z',
        settings: {
            is_public: true,
            is_trial: false
        },
        self: {
            href: 'https://api.typeform.com/forms/obZZBjd4'
        },
        theme: {
            href: 'https://api.typeform.com/themes/qHWOQ7'
        },
        _links: {
            display: 'https://grntn54tvzi.typeform.com/to/obZZBjd4'
        }
    }
];

export const importTypeformMock = {
    id: 'UJs4vZ7O',
    type: 'quiz',
    title: 'All Fields',
    workspace: {
        href: 'https://api.typeform.com/workspaces/nyEQis'
    },
    theme: {
        href: 'https://api.typeform.com/themes/qHWOQ7'
    },
    settings: {
        language: 'en',
        progress_bar: 'proportion',
        meta: {
            allow_indexing: false
        },
        hide_navigation: false,
        is_public: true,
        is_trial: false,
        show_progress_bar: true,
        show_typeform_branding: true,
        are_uploads_public: false,
        show_time_to_complete: true,
        show_number_of_submissions: false,
        show_cookie_consent: false,
        show_question_number: true,
        show_key_hint_on_choices: true,
        autosave_progress: true,
        pro_subdomain_enabled: false,
        capabilities: {
            e2e_encryption: {
                enabled: false,
                modifiable: false
            }
        }
    },
    thankyou_screens: [
        {
            id: 'BT28Wp5ogZtU',
            ref: '01GQ25H571DX3NAK4ED5TDCF6R',
            title: '',
            type: 'thankyou_screen',
            properties: {
                show_button: true,
                share_icons: true,
                button_mode: 'default_redirect',
                button_text: 'Create a typeform'
            }
        },
        {
            id: 'DefaultTyScreen',
            ref: 'default_tys',
            title: "Thanks for completing this typeform\nNow *create your own* — it's free, easy, & beautiful",
            type: 'thankyou_screen',
            properties: {
                show_button: true,
                share_icons: false,
                button_mode: 'default_redirect',
                button_text: 'Create a *typeform*'
            },
            attachment: {
                type: 'image',
                href: 'https://images.typeform.com/images/2dpnUBBkz2VN'
            }
        }
    ],
    fields: [
        {
            id: 'Cuvf8MoynrBC',
            title: 'Choice Question (Optional )',
            ref: '01GQ25H571FH1DBVZD07CXSSSY',
            properties: {
                description: 'Description of question',
                randomize: false,
                allow_multiple_selection: false,
                allow_other_choice: false,
                vertical_alignment: true,
                choices: [
                    {
                        id: 'K72rC2mI9Aaz',
                        ref: '01GQ25H571WPK08PAQP94R46PP',
                        label: '1'
                    },
                    {
                        id: 'YhOqTj5CBd7s',
                        ref: '01GQ25H5711D10VAAZQX1P66HM',
                        label: '2'
                    },
                    {
                        id: '9vh8nMZSsxpc',
                        ref: '4f5cd9c0-46f9-41fc-bf55-16f2fc16ea5a',
                        label: '3'
                    }
                ]
            },
            validations: {
                required: false
            },
            type: 'multiple_choice',
            attachment: {
                type: 'image',
                href: 'https://images.typeform.com/images/WMALzu59xbXQ'
            },
            layout: {
                type: 'split',
                attachment: {
                    type: 'image',
                    href: 'https://images.typeform.com/images/WMALzu59xbXQ'
                }
            }
        },
        {
            id: 'z6x3HSdq8viG',
            title: 'Short Answer',
            ref: '1dfb94a7-b5f9-4595-90a5-e2281a51f96e',
            properties: {
                description: 'Description'
            },
            validations: {
                required: false
            },
            type: 'short_text'
        },
        {
            id: 'LGhCtilmLwXn',
            title: 'Date ',
            ref: '875a003d-a555-4dfc-90a3-e6769cac6634',
            properties: {
                separator: '/',
                structure: 'MMDDYYYY'
            },
            validations: {
                required: false
            },
            type: 'date'
        },
        {
            id: 'uLtGKgh0OpBj',
            title: 'Grid Questions',
            ref: '9d95a671-ef51-4c07-8c81-3ff45994f81a',
            properties: {
                fields: [
                    {
                        id: 'OihfIaL3z5Ao',
                        title: 'Row1',
                        ref: '3300e5b8-9c06-4a5d-9069-e49d1a2b5b3a',
                        properties: {
                            randomize: false,
                            allow_multiple_selection: false,
                            allow_other_choice: false,
                            vertical_alignment: true,
                            choices: [
                                {
                                    id: 'JJ8VpplyhRRi',
                                    ref: '17e91a45-1141-4b0c-a746-6e8172796fdf',
                                    label: 'Col1'
                                },
                                {
                                    id: 'Nc0JrRu4f3qM',
                                    ref: '9b028ba2-df49-4e27-8158-cf8914a948aa',
                                    label: 'Col2'
                                },
                                {
                                    id: 'X07o5GRKDJ4Q',
                                    ref: '922e34cd-2e61-4978-8ab7-0051f3b58b82',
                                    label: 'Col3'
                                }
                            ]
                        },
                        validations: {
                            required: false
                        },
                        type: 'multiple_choice'
                    },
                    {
                        id: 'u9UUWR1CEhF7',
                        title: 'Row2',
                        ref: 'bebe9a73-1f13-4212-9c55-28b55f760ea6',
                        properties: {
                            randomize: false,
                            allow_multiple_selection: false,
                            allow_other_choice: false,
                            vertical_alignment: true,
                            choices: [
                                {
                                    id: 'HVtzfvCONZ0B',
                                    ref: 'e910d321-e87b-4021-9039-a21b8833432e',
                                    label: 'Col1'
                                },
                                {
                                    id: '8wTJKklTewHd',
                                    ref: '75514fea-f55d-451d-99e6-6b059ef64663',
                                    label: 'Col2'
                                },
                                {
                                    id: 'E3QMRUnNDShP',
                                    ref: '6829bb9b-5900-4a68-8051-f2ad7f29b130',
                                    label: 'Col3'
                                }
                            ]
                        },
                        validations: {
                            required: false
                        },
                        type: 'multiple_choice'
                    },
                    {
                        id: 'IullXQme3jtv',
                        title: 'Row',
                        ref: '80239b30-f4c7-4bbc-af64-1bacfb0ede28',
                        properties: {
                            randomize: false,
                            allow_multiple_selection: false,
                            allow_other_choice: false,
                            vertical_alignment: true,
                            choices: [
                                {
                                    id: 'kTkNCdSxtC4b',
                                    ref: '0716f188-b83c-4ccd-87a0-2c162887d44f',
                                    label: 'Col1'
                                },
                                {
                                    id: 'p1awHzqQqdvK',
                                    ref: '834a3ec8-7b41-4d42-a366-aa62bc123275',
                                    label: 'Col2'
                                },
                                {
                                    id: 'OjRBCKwL67Av',
                                    ref: 'bb404f2b-3c23-47e5-9488-eae437bd95a6',
                                    label: 'Col3'
                                }
                            ]
                        },
                        validations: {
                            required: false
                        },
                        type: 'multiple_choice'
                    }
                ]
            },
            type: 'matrix'
        },
        {
            id: 'gJtwFUH2OOj2',
            title: 'Grid Checkbox',
            ref: '6f3cf9f2-b87a-4ede-a66f-e4286430249f',
            properties: {
                fields: [
                    {
                        id: 'udsJDGU6anWj',
                        title: 'row1',
                        ref: 'f0d42d2e-9009-4f00-8277-df8afa99e6ff',
                        properties: {
                            randomize: false,
                            allow_multiple_selection: true,
                            allow_other_choice: false,
                            vertical_alignment: true,
                            choices: [
                                {
                                    id: 'SV6u3LrEy2Cv',
                                    ref: '166f5976-3b52-470d-9d7c-fb5fb3f6de26',
                                    label: 'col1'
                                },
                                {
                                    id: 'g5ytyG9ArEIj',
                                    ref: 'fc9a1967-6a06-4b3a-a9e6-f41b5725072f',
                                    label: 'col2'
                                },
                                {
                                    id: 'HGUX7ggneuqd',
                                    ref: 'bc44cb4e-d804-468e-b469-b7a31877f6bb',
                                    label: 'col3'
                                }
                            ]
                        },
                        validations: {
                            required: false
                        },
                        type: 'multiple_choice'
                    },
                    {
                        id: 'tvY1F1bLO437',
                        title: 'row2',
                        ref: '2985e14a-b2d6-4c4c-ba9b-4aad00bc8ae3',
                        properties: {
                            randomize: false,
                            allow_multiple_selection: true,
                            allow_other_choice: false,
                            vertical_alignment: true,
                            choices: [
                                {
                                    id: 'Ofm7Ho82Plma',
                                    ref: '98b03c3a-664d-407d-9620-323edf693d0a',
                                    label: 'col1'
                                },
                                {
                                    id: 'UySZNqJwZ02E',
                                    ref: '0e7edc32-a71a-4e7c-8679-bccd151fac24',
                                    label: 'col2'
                                },
                                {
                                    id: 'ndJO4DnZbBkI',
                                    ref: '3d1ee9c8-3ce7-48f4-8fd6-75ae0fd9cddf',
                                    label: 'col3'
                                }
                            ]
                        },
                        validations: {
                            required: false
                        },
                        type: 'multiple_choice'
                    },
                    {
                        id: 'RHjLUyoYWOc2',
                        title: 'row3',
                        ref: '362f5129-cb4b-4c62-873b-d7b782d0bb8b',
                        properties: {
                            randomize: false,
                            allow_multiple_selection: true,
                            allow_other_choice: false,
                            vertical_alignment: true,
                            choices: [
                                {
                                    id: 'M9GbrdQHMuNp',
                                    ref: '34daa3d6-74e5-4510-9a7b-c87be0c73259',
                                    label: 'col1'
                                },
                                {
                                    id: '4X4xncwNa69t',
                                    ref: '09734898-846a-43c0-8205-cb060c21f349',
                                    label: 'col2'
                                },
                                {
                                    id: 'gVYNyJPm4yL3',
                                    ref: '1cf709cd-0879-4eba-9e4f-533f14806823',
                                    label: 'col3'
                                }
                            ]
                        },
                        validations: {
                            required: false
                        },
                        type: 'multiple_choice'
                    },
                    {
                        id: '8TkjvuLpaDCT',
                        title: 'row3',
                        ref: '7c578cff-c346-4c8c-9880-a0f90dc5aab7',
                        properties: {
                            randomize: false,
                            allow_multiple_selection: true,
                            allow_other_choice: false,
                            vertical_alignment: true,
                            choices: [
                                {
                                    id: 'mEoqmPjiN1ab',
                                    ref: '4d5a03aa-8130-4547-96b7-c11df8ed7b44',
                                    label: 'col1'
                                },
                                {
                                    id: 'NP5xY59JWlrO',
                                    ref: '5e2c76a8-e1e9-4749-8176-2f66576ed934',
                                    label: 'col2'
                                },
                                {
                                    id: 'opuOaHh9BtmR',
                                    ref: 'd7af7575-35a9-4c93-9738-7e7c4926e0ac',
                                    label: 'col3'
                                }
                            ]
                        },
                        validations: {
                            required: false
                        },
                        type: 'multiple_choice'
                    }
                ]
            },
            type: 'matrix'
        },
        {
            id: 'n1eGew9fgdAI',
            title: 'How likely are you to recommend us to a friend or colleague?',
            ref: 'a34117bc-2338-4fd0-b9cc-bb818549efe3',
            properties: {
                steps: 11
            },
            validations: {
                required: false
            },
            type: 'nps'
        },
        {
            id: 'lr5MtZ7lhSMj',
            title: 'Sort',
            ref: 'b4633224-4d88-4804-9d96-aeb547ec8e25',
            properties: {
                randomize: false,
                allow_multiple_selection: true,
                choices: [
                    {
                        id: 'DoHFs0CDamkU',
                        ref: '6c2de56d-4269-4a76-8161-bf1563e1f37b',
                        label: '1'
                    },
                    {
                        id: 'SA9paoqZqVQc',
                        ref: '1bc0b15e-7099-474d-b1f4-083351c59936',
                        label: '10'
                    },
                    {
                        id: '559O0Rm8NnhD',
                        ref: 'fc7fe8b8-6a35-4696-96b5-31a743fd3c04',
                        label: '6'
                    },
                    {
                        id: 'hmU9b4PnhfHg',
                        ref: '064636bb-f489-4631-bb50-cbf407e2c2b3',
                        label: '10'
                    }
                ]
            },
            validations: {
                required: false
            },
            type: 'ranking'
        },
        {
            id: 'Nt0u8M5M3afh',
            title: 'Rate Our Services',
            ref: '244288b6-bb3c-4ead-973a-ceed837dd666',
            properties: {
                shape: 'star',
                steps: 10
            },
            validations: {
                required: false
            },
            type: 'rating'
        },
        {
            id: '3Lt2vAms4JXT',
            title: 'Multiple Choice Question (Checkboxes)',
            ref: 'c76cb85e-715a-4dda-91ca-85c6c3870607',
            properties: {
                description: 'Description',
                randomize: false,
                allow_multiple_selection: true,
                allow_other_choice: false,
                vertical_alignment: true,
                choices: [
                    {
                        id: 'ZRRyvVHZVA5Q',
                        ref: 'ff30de08-b06e-46a7-bae2-47a9370b7930',
                        label: '1'
                    },
                    {
                        id: 'ifumgopG5Zjo',
                        ref: 'bc2c5ac7-1b20-47a3-bed3-5740b9e8e5db',
                        label: '2'
                    },
                    {
                        id: 'MV5DQz2iGttl',
                        ref: '44bb7c9c-f6e0-48e3-a9f4-e8e443c060f1',
                        label: '3'
                    },
                    {
                        id: 'n1b2S5iFwOkV',
                        ref: 'af294cb5-1058-450c-b95c-0001a1d14e47',
                        label: '4'
                    }
                ]
            },
            validations: {
                required: false
            },
            type: 'multiple_choice'
        },
        {
            id: 'IPqwBDKoMBaN',
            title: 'Write a long answer',
            ref: '81b80aef-6286-4cef-b957-6da18319fa5c',
            properties: {
                description: 'Description'
            },
            validations: {
                required: false
            },
            type: 'long_text'
        },
        {
            id: '1byeQnhaY7I1',
            title: 'This is a statement',
            ref: '7c30d865-a50a-46d0-a3c1-f3d012504f2e',
            properties: {
                description: 'Description of the statemant',
                button_text: 'Continue',
                hide_marks: false
            },
            type: 'statement'
        },
        {
            id: 'FGEvPD7iAvGf',
            title: 'Yes/No',
            ref: '959b76b4-5314-4a47-bb61-4c77f193fec8',
            properties: {},
            validations: {
                required: false
            },
            type: 'yes_no'
        },
        {
            id: 'wHqnoGTRGceY',
            title: 'Your Address',
            ref: 'b5cf78aa-2110-4f0b-9990-10c843e15013',
            properties: {
                fields: [
                    {
                        id: 'BTYRupNpvSB5',
                        title: 'Address',
                        ref: '077375fb-fab1-4c5d-b3ed-ca79b3bb9c41',
                        subfield_key: 'address',
                        properties: {},
                        validations: {
                            required: false,
                            max_length: 250
                        },
                        type: 'short_text'
                    },
                    {
                        id: 'DFoHi12vsgk9',
                        title: 'Address line 2',
                        ref: '90d08c67-3a21-4e67-b6e4-1407a22cec51',
                        subfield_key: 'address_line_2',
                        properties: {},
                        validations: {
                            required: false,
                            max_length: 250
                        },
                        type: 'short_text'
                    },
                    {
                        id: 'DKZjPR9a0pEY',
                        title: 'City/Town',
                        ref: 'b4b5d394-5256-4c74-ab49-20223751a9fa',
                        subfield_key: 'city',
                        properties: {},
                        validations: {
                            required: false,
                            max_length: 250
                        },
                        type: 'short_text'
                    },
                    {
                        id: '2VP5IuTZdRdI',
                        title: 'State/Region/Province',
                        ref: '7b4209c0-9b12-4678-bb64-7cfd72d835f5',
                        subfield_key: 'state',
                        properties: {},
                        validations: {
                            required: false,
                            max_length: 250
                        },
                        type: 'short_text'
                    },
                    {
                        id: '3qZyQmHMd73a',
                        title: 'Zip/Post Code',
                        ref: '12f54ecf-2cd0-4146-9a5a-c7b4f14620ac',
                        subfield_key: 'zip_code',
                        properties: {},
                        validations: {
                            required: false,
                            max_length: 250
                        },
                        type: 'short_text'
                    },
                    {
                        id: 'aLTbbVbuiY3P',
                        title: 'Country',
                        ref: 'e41ba749-3e80-461c-95b5-2077c06e97a0',
                        subfield_key: 'country',
                        properties: {},
                        validations: {
                            required: false,
                            max_length: 250
                        },
                        type: 'short_text'
                    }
                ]
            },
            type: 'address'
        },
        {
            id: 'FYkuWIxdoTQs',
            title: 'Contact Information',
            ref: '21ba58c9-1963-417e-885a-dc6335587eab',
            properties: {
                description: 'Contact Description',
                fields: [
                    {
                        id: 'iHoVRt3sRtNn',
                        title: 'First name',
                        ref: '37b30a65-ea59-4107-a67f-2b7496e89deb',
                        subfield_key: 'first_name',
                        properties: {},
                        validations: {
                            required: false
                        },
                        type: 'short_text'
                    },
                    {
                        id: 'NnFUmxBi3ekS',
                        title: 'Last name',
                        ref: '33a60d84-80b1-447c-b4d6-166051337e35',
                        subfield_key: 'last_name',
                        properties: {},
                        validations: {
                            required: false
                        },
                        type: 'short_text'
                    },
                    {
                        id: 'Sxnj52MrAu6P',
                        title: 'Phone number',
                        ref: '41e8e077-97f6-45ee-ad9e-296002c00841',
                        subfield_key: 'phone_number',
                        properties: {
                            default_country_code: 'US'
                        },
                        validations: {
                            required: false
                        },
                        type: 'phone_number'
                    },
                    {
                        id: '2TmDGiAPoh4Z',
                        title: 'Email',
                        ref: 'fce90165-e304-49e6-98cf-33be52287511',
                        subfield_key: 'email',
                        properties: {},
                        validations: {
                            required: false
                        },
                        type: 'email'
                    },
                    {
                        id: '0vrSWgwXRVmc',
                        title: 'Company',
                        ref: 'fa63f578-a09e-4229-948a-c0231e23d7be',
                        subfield_key: 'company',
                        properties: {},
                        validations: {
                            required: false
                        },
                        type: 'short_text'
                    }
                ]
            },
            type: 'contact_info'
        },
        {
            id: 'bGcDUaOhea3u',
            title: 'Enter your email',
            ref: 'ba0c6b71-a402-4072-9dcd-2d2d93ac86c4',
            properties: {
                description: 'Descriptions'
            },
            validations: {
                required: false
            },
            type: 'email'
        },
        {
            id: 'n2N93QubJsRi',
            title: 'Your Phone Number',
            ref: 'ac969103-e4d3-4abf-b263-469800d3341c',
            properties: {
                default_country_code: 'US'
            },
            validations: {
                required: false
            },
            type: 'phone_number'
        },
        {
            id: '5smadFbNNuVd',
            title: 'Your Website',
            ref: 'df6f3b8b-f72a-4298-94ca-26976a26e85f',
            properties: {},
            validations: {
                required: false
            },
            type: 'website'
        },
        {
            id: 'aqEIH3HjpGpS',
            title: 'Dropdown',
            ref: '147acc9b-2d18-4e49-887f-0bf5feebbec4',
            properties: {
                randomize: false,
                alphabetical_order: false,
                choices: [
                    {
                        id: 'L147fYmu4opA',
                        ref: 'bc5861a1-3b81-4caa-939d-fb10e31ad996',
                        label: '1'
                    },
                    {
                        id: 'O0avAnQ5anH7',
                        ref: '00d5653e-97de-40ce-b459-a1f5479743b6',
                        label: '2'
                    },
                    {
                        id: '1tAt9zC30Kc5',
                        ref: 'e37f898d-0e4f-4128-9afa-7e44dbd5a800',
                        label: '3'
                    },
                    {
                        id: 'aor8LTJlBtXe',
                        ref: '49b3a986-04af-4929-bdeb-fdb7d449df0e',
                        label: '4'
                    },
                    {
                        id: 'unhRtnYf7Bjs',
                        ref: '8b361e7c-53b2-4c00-9ad6-4ca4b66c0eb7',
                        label: '5'
                    },
                    {
                        id: 'MHod62gfG72L',
                        ref: 'ce88952e-a96a-4c53-901e-42e65a54282f',
                        label: '6'
                    }
                ]
            },
            validations: {
                required: false
            },
            type: 'dropdown'
        },
        {
            id: 'TLvTFtv7Jhx1',
            title: '...',
            ref: 'd7b309fd-946a-4513-86e3-b8ecc9078237',
            properties: {
                button_text: 'Continue',
                show_button: true,
                fields: [
                    {
                        id: 'kCk9maHvbqVz',
                        title: '...',
                        ref: '0a4d903c-2e03-46f7-861f-e54ebca4fc89',
                        properties: {},
                        validations: {
                            required: false
                        },
                        type: 'short_text'
                    }
                ]
            },
            type: 'group'
        },
        {
            id: '31PZaDIEr8uo',
            title: 'Group of questions',
            ref: 'add918ca-47b6-4671-89a1-a27d27775efd',
            properties: {
                button_text: 'Continue',
                show_button: true,
                fields: [
                    {
                        id: 'SnZ3eUQSTaTI',
                        title: 'Short Question',
                        ref: '71e4a594-1424-4503-b8f6-3b9582c16f34',
                        properties: {},
                        validations: {
                            required: false
                        },
                        type: 'short_text'
                    },
                    {
                        id: 'LOEf2oJzVPyA',
                        title: 'Website',
                        ref: '73f7a16d-b751-4b24-a0c7-f1f9e9d8f4f9',
                        properties: {},
                        validations: {
                            required: false
                        },
                        type: 'website'
                    },
                    {
                        id: 'tKSeTOvpPkQd',
                        title: '...',
                        ref: 'e98355b9-09f7-44be-ae57-8ec8d7e28b5c',
                        properties: {},
                        validations: {
                            required: false
                        },
                        type: 'short_text'
                    }
                ]
            },
            type: 'group'
        }
    ],
    created_at: '2023-01-18T10:06:57+00:00',
    last_updated_at: '2023-01-18T10:36:19+00:00',
    published_at: '2023-01-18T10:36:19+00:00',
    _links: {
        display: 'https://grntn54tvzi.typeform.com/to/UJs4vZ7O'
    }
};
