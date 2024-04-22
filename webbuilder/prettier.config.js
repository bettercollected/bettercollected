module.exports = {
    printWidth: 88,
    singleQuote: true,
    tabWidth: 4,
    trailingComma: 'none',
    importOrder: [
        '^(?:react)$',
        '^(?:next|next/?.*)$',
        '^(?:_|clsx|fs|lodash/?.*|path)$',
        '<THIRD_PARTY_MODULES>',
        '^@app/(.*)$',
        '^[./]'
    ],
    tailwindAttributes: ['className'],
    plugins: ['@trivago/prettier-plugin-sort-imports', 'prettier-plugin-tailwindcss'],
    importOrderSeparation: true,
    importOrderSortSpecifiers: true
};
