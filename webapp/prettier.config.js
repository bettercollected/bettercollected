module.exports = {
    printWidth: 256,
    singleQuote: true,
    tabWidth: 4,
    trailingComma: 'none',
    importOrder: ['^(?:react)$', '^(?:next|next/?.*)$', '^(?:_|clsx|fs|lodash/?.*|path)$', '<THIRD_PARTY_MODULES>', '^@app/(.*)$', '^[./]'],
    importOrderSeparation: true,
    importOrderSortSpecifiers: true
};
