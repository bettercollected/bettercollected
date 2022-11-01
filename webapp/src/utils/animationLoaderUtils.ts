export const getAnimatedCards = (count: number = 12) => {
    const cards = [];
    for (let i = 0; i < count; i++) {
        cards.push(i);
    }
    return cards;
};
