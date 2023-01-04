export default function Checkboxes() {
    const options = ['Bacon', 'Egg', 'Meat', 'Fish'];
    return (
        <div className="mb-4">
            <h3 className="text-lg mb-2 font-medium">Checkboxes</h3>
            {options.map((a) => (
                <div key={a} className="flex items-center mb-2">
                    <input
                        id="default-checkbox"
                        type="checkbox"
                        value=""
                        disabled
                        className="w-6 h-6 text-blue-600 rounded border-[#eaeaea] focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
                    />
                    <label htmlFor="default-checkbox" className="ml-2 text-lg text-gray-700 dark:text-gray-300">
                        {a}
                    </label>
                </div>
            ))}
        </div>
    );
}
