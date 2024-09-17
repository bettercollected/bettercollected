import { useState } from 'react';

export default function useForm() {
    const [isLoading, setLoading] = useState(false);
    const [error, setError] = useState(false);
    return { isLoading, error, setLoading, setError };
}