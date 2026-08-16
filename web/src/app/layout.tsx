export const metadata = {
  title: "AgentTrace",
  description: "Observer UI for the AgentTrace multi-stage agent",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}