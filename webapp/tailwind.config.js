const defaultTheme = require('tailwindcss/defaultTheme');

module.exports = {
    content: ['./src/**/*.{js,ts,jsx,tsx}'],
    darkMode: 'class',
    theme: {
        screens: {
            xs: '360px',
            '2xs': '480px',
            sm: '640px',
            md: '768px',
            lg: '1024px',
            xl: '1280px',
            '2xl': '1536px'
        },
        extend: {
            blur: {
                dashboardBackground: '105px'
            },

            colors: {
                dropdown: {
                    shadow: 'rgba(19, 73, 179, 0.25)'
                },
                new: {
                    black: {
                        100: '#F6F6F6',
                        200: '#EEEEEE',
                        300: '#DBDBDB',
                        400: '#CED4DA',
                        500: '#ADB5BD',
                        600: '#6C757D',
                        700: '#495057',
                        800: '#4D4D4D',
                        900: '#2E2E2E',

                        DEFAULT: '#2E2E2E'
                    },
                    blue: {
                        100: '#F2F7FF',
                        200: '#B8D5FF',
                        300: '#A2C5F8',
                        500: '#0764EB'
                    },
                    pink: {
                        DEFAULT: '#FE3678'
                    },
                    orange: {
                        DEFAULT: '#FFA716'
                    }
                },
                // brand: 'rgb(var(--color-brand) / <alpha-value>)',
                dark: '#1c1917',
                success: '#B5F4AF',
                'light-dark': '#171e2e',
                white: '#ffffff',
                brand: {
                    100: '#F2F7FF',
                    200: '#D8E8FF',
                    300: '#A8C6F0',
                    400: '#82A2CF',
                    500: '#0764EB',
                    600: '#0C50B4',
                    700: '#2C2C60',
                    800: '#11114C',
                    900: '#111134',

                    DEFAULT: '#0764EB'
                },
                'brand-accent': {
                    500: '#F8B940',
                    600: '#E79B0B',

                    DEFAULT: '#F8B940'
                },
                black: {
                    100: '#F8F9FA',
                    200: '#E9ECEF',
                    300: '#DEE2E6',
                    400: '#CED4DA',
                    500: '#ADB5BD',
                    600: '#6C757D',
                    700: '#495057',
                    800: '#343A40',
                    900: '#212529',

                    DEFAULT: '#ADB5BD'
                },
                red: {
                    100: '#FFECE7',
                    500: '#EA400E',
                    DEFAULT: '#EA400E'
                },
                orange: {
                    500: '#EB8E07',
                    DEFAULT: '#EB8E07'
                },
                pink: {
                    DEFAULT: '#FE3678'
                }
            },
            spacing: {
                13: '3.375rem'
            },
            margin: {
                '1/2': '50%'
            },
            padding: {
                full: '100%'
            },
            width: {
                'calc-320': 'calc(100% - 320px)',
                'calc-358': 'calc(100% - 358px)',
                '289-calc-289': 'calc(100vh - 592px)',
                'calc-289': 'calc(100% - 578px)'
            },
            maxWidth: {
                '289-calc-289': 'calc(100vw - 592px)'
            },
            minHeight: {
                'calc-68': 'calc(100vh - 68px)'
            },
            borderWidth: {
                3: '3px'
            },
            boxShadow: {
                main: '0px 6px 18px rgba(0, 0, 0, 0.04)',
                light: '0px 4px 4px rgba(0, 0, 0, 0.08)',
                large: '0px 8px 16px rgba(17, 24, 39, 0.1)',
                card: '0px 2px 6px rgba(0, 0, 0, 0.06)',
                transaction: '0px 8px 16px rgba(17, 24, 39, 0.06)',
                formCard: '0px 0px 30px rgba(3, 3, 80, 0.08)',
                button: '0px 2px 4px rgba(0, 0, 0, 0.06), 0px 4px 6px rgba(0, 0, 0, 0.1)',
                logoCard: '0px 0px 40px 0px rgba(19, 73, 179, 0.25)'
            },
            dropShadow: {
                paper: '0px 0px 15px rgba(0, 0, 0, 0.15)',
                main: '0px 4px 8px rgba(0, 0, 0, 0.08)'
            },
            backgroundImage: {
                'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
                'sign-in': "url('/images/background.png')"
            },
            animation: {
                blink: 'blink 1.4s infinite both;',
                'spin-slow': 'spinSlow 5s linear infinite',
                'move-up': 'moveUp 500ms infinite alternate',
                'scale-up': 'scaleUp 500ms infinite alternate',
                'scale-down': 'scaleDown 500ms infinite alternate',
                'drip-expand': 'expand 500ms ease-in forwards',
                'drip-expand-large': 'expand-large 600ms ease-in forwards',
                'move-up-small': 'moveUpSmall 500ms infinite alternate',
                wiggle: 'wiggle 1s ease-in-out infinite'
            },
            keyframes: {
                blink: {
                    '0%': { opacity: 0.2 },
                    '20%': { opacity: 1 },
                    '100%': { opacity: 0.2 }
                },
                spinSlow: {
                    '0%': { transform: 'rotate3d(0, 1, 0, 0deg)' },
                    '25%': { transform: 'rotate3d(0, 1, 0, 90deg)' },
                    '50%': { transform: 'rotate3d(0, 1, 0, 180deg)' },
                    '75%': { transform: 'rotate3d(0, 1, 0, 270deg)' },
                    '100%': { transform: 'rotate3d(0, 1, 0, 360deg)' }
                },
                wiggle: {
                    '0%, 100%': { transform: 'rotate(-3deg)' },
                    '50%': { transform: 'rotate(3deg)' }
                },
                expand: {
                    '0%': {
                        opacity: 0,
                        transform: 'scale(1)'
                    },
                    '30%': {
                        opacity: 1
                    },
                    '80%': {
                        opacity: 0.5
                    },
                    '100%': {
                        transform: 'scale(30)',
                        opacity: 0
                    }
                },
                'expand-large': {
                    '0%': {
                        opacity: 0,
                        transform: 'scale(1)'
                    },
                    '30%': {
                        opacity: 1
                    },
                    '80%': {
                        opacity: 0.5
                    },
                    '100%': {
                        transform: 'scale(96)',
                        opacity: 0
                    }
                },
                moveUp: {
                    '0%': { transform: 'translateY(0)' },
                    '100%': { transform: 'translateY(-20px)' }
                },
                moveUpSmall: {
                    '0%': { transform: 'translateY(0)' },
                    '100%': { transform: 'translateY(-10px)' }
                },
                scaleDown: {
                    '0%': { transform: 'scale(0)' },
                    '100%': { transform: 'scale(1)' }
                },
                scaleUp: {
                    '100%': { transform: 'scale(1.1)' },
                    '0%': { transform: 'scale(1)' }
                }
            },
            screens: {
                xs: '360px',
                '2xs': '480px',
                sm: '640px',
                md: '768px',
                lg: '1024px',
                xl: '1280px',
                '2xl': '1536px'
            },
            fontFamily: {
                inter: ['Inter', 'Open Sans', 'monospace'],
                roboto: ['Roboto', 'Inter', 'Open Sans', 'monospace']
            },
            fontSize: {
                xs: ['0.75rem', { lineHeight: '1rem' }],
                sm: ['0.875rem', { lineHeight: '1.25rem' }],
                base: ['1rem', { lineHeight: '1.5rem' }],
                lg: ['1.125rem', { lineHeight: '1.75rem' }],
                xl: ['1.25rem', { lineHeight: '1.75rem' }],
                '2xl': ['1.5rem', { lineHeight: '2rem' }],
                '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
                '4xl': ['2.25rem', { lineHeight: '2.5rem' }],
                '5xl': ['3rem', { lineHeight: '1' }],
                '6xl': ['3.75rem', { lineHeight: '1' }],
                '7xl': ['4.5rem', { lineHeight: '1' }],
                '8xl': ['6rem', { lineHeight: '1' }],
                '9xl': ['8rem', { lineHeight: '1' }]
            },
            fontWeight: {
                thin: '100',
                extralight: '200',
                light: '300',
                normal: '400',
                medium: '500',
                semibold: '600',
                bold: '700',
                extrabold: '800',
                black: '900'
            },
            aspectRatio: {
                'banner-desktop': '5.14285714 / 1',
                'banner-mobile': '3 / 1',
                'editable-banner-desktop': '3.9886363636 / 1',
                'editable-banner-mobile': '2 / 1',
                thank_you_cover: '59 / 10'
            }
        }
    },
    variants: {
        extends: {
            scrollbar: ['rounded']
        }
    },
    plugins: [
        require('@tailwindcss/typography'),
        require('@tailwindcss/forms'),
        require('@tailwindcss/line-clamp'),
        require('tailwind-scrollbar')({ nocompatible: true }),
        ({ addComponents }) => {
            addComponents({
                '.container': {
                    maxWidth: '100%',
                    '@screen xs': {
                        maxWidth: '360px'
                    },
                    '@screen 2xs': {
                        maxWidth: '440px'
                    },
                    '@screen sm': {
                        maxWidth: '670px'
                    },
                    '@screen md': {
                        maxWidth: '800px'
                    },
                    '@screen lg': {
                        maxWidth: '1176px'
                    },
                    '@screen xl': {
                        maxWidth: '1310px'
                    },
                    '@screen 2xl': {
                        maxWidth: '1352px'
                    }
                }
            });
        }
    ]
};
