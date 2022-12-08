export default function RadioButton() {
    const options = ['Bacon', 'Chicken', 'Mutton'];
    return (
        <div className="mb-4">
            <h3 className="text-lg mb-2 font-medium">Multiple Choice</h3>
            <div className="flex flex-col mb-2">
                {options.map((a, idx) => (
                    <div key={idx}>
                        <input id="default-radio-1" disabled type="radio" value="" name="default-radio" className="w-4 h-4 ring-0 active:bg-red focus:ring-offset-0 focus:ring-0 text-blue-600 border-[#eaeaea]" />
                        <label htmlFor="default-radio-1" className="ml-2 text-sm font-medium text-gray-900 dark:text-gray-300">
                            {a}
                        </label>
                    </div>
                ))}
            </div>
        </div>
    );
}
