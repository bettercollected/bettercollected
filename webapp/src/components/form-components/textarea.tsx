export default function TextArea() {
    return (
        <div className="mb-4">
            <label htmlFor="message" className="text-lg block mb-2 font-medium">
                Text Area
            </label>
            <textarea id="message" rows={4} className="block p-2.5  w-full lg:w-1/2 text-md text-gray-900 rounded-md border-[1px] border-solid border-[#eaeaea]" placeholder="Enter your description here..." />
        </div>
    );
}
