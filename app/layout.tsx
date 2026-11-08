import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'RoleReady | Interview preparation',
  description: 'Turn your resume into an actionable interview practice session.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
