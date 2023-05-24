export function generateRandomBgColor() {
    // const colors = ['bg-[#EB8E07]', 'bg-[#13CBDE]', 'bg-[#0764EB]', 'bg-[#D27D00]', 'bg-[#2C2C60]', 'bg-[#CA3A10]', 'bg=[#EA400E]', 'bg-[#6C757D]'];
    // const randomIndex = Math.floor(Math.random() * colors.length);
    // return colors[randomIndex];

    const color = Math.floor(Math.random() * 16777215).toString(16);
    return `#${color}`;
}
