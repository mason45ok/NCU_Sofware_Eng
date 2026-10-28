import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import type { z } from 'zod';

/** React Hook Form＋Zod：驗證規則與 TypeScript 型別共用。 */
export function useZodForm<S extends z.ZodTypeAny>(schema: S, defaultValues?: z.infer<S>) {
  return useForm<z.infer<S>>({ resolver: zodResolver(schema), defaultValues });
}
