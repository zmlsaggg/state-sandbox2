import { Toaster } from '@/components/ui/toaster';
import { UserProvider } from '@/context/user-context';
import '@fontsource-variable/inter';
import '@fontsource-variable/geist-mono';
import './globals.css';

export const metadata = {
  title: 'State Sandbox AI',
  description:
    'State Sandbox AI is a political simulation game powered by o3-mini',
  manifest: '/manifest.json',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="antialiased"
        style={{ '--font-inter': 'Inter Variable', '--font-geist-mono': 'Geist Mono Variable' }}>
        <UserProvider>
          {children}
          <Toaster />
        </UserProvider>
      </body>
    </html>
  );
}
