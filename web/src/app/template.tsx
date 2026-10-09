/** Each page fades in when it opens; the layout (header and footer) stays still. */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="animate-fade-in">{children}</div>;
}
