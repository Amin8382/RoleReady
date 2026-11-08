import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RoleReady — Make your next interview count",
  description: "Prepare for your next role with focused interview practice, clear feedback, and a personal cheat sheet.",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
