import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: import.meta.dirname });

const config = [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts", "src/lib/api/schema.d.ts"] },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default config;
