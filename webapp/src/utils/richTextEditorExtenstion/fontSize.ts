import { Extension } from '@tiptap/core';
import '@tiptap/extension-text-style';

export type FontSizeOptions = {
    types: string[];
};

declare module '@tiptap/core' {
    interface Commands<ReturnType> {
        fontSize: {
            /**
             * Set the font size
             */
            setFontSize: (fontSize: string) => ReturnType;
            /**
             * Unset the font size
             */
            unsetFontSize: () => ReturnType;
        };
    }
}

export const FontSize = Extension.create<FontSizeOptions>({
    name: 'fontSize',

    addOptions() {
        return {
            types: ['textStyle']
        };
    },

    addGlobalAttributes() {
        return [
            {
                name: 'fontSize',
                types: this.options.types,
                attributes: {
                    fontSize: {
                        default: {
                            style: `font-size: 16px; font-weight:600; line-height:24px`
                        },
                        parseHTML: (element) =>
                            element.style.fontSize.replace(/['"]+/g, ''),
                        renderHTML: (attributes) => {
                            if (!attributes.fontSize) {
                                return {};
                            }

                            return {
                                style: `font-size: ${attributes.fontSize}${attributes.fontSize.includes('px') ? '' : 'px'}; line-height: calc(1.5 * ${attributes.fontSize}${attributes.fontSize.includes('px') ? '' : 'px'})`
                            };
                        }
                    }
                }
            }
        ];
    },

    addCommands() {
        return {
            setFontSize:
                (fontSize) =>
                ({ chain }) => {
                    return chain().setMark('textStyle', { fontSize }).run();
                },
            unsetFontSize:
                () =>
                ({ chain }) => {
                    return chain()
                        .setMark('textStyle', { fontSize: '16px' })
                        .removeEmptyTextStyle()
                        .run();
                }
        };
    }
});
